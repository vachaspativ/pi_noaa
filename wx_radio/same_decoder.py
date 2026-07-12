"""
Parses SAME (Specific Area Message Encoding) data strings into structured alerts.
Can decode from WAV file via multimon-ng subprocess, or parse raw strings.
"""
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List

from wx_radio.same_codes import SAME_EVENT_CODES
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)

# Standard SAME regex pattern
# ZCZC-ORG-EEE-PSSCCC-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-
# ZCZC: start of message
# ORG: Originator (WXR for NWS)
# EEE: Event code (TOR for Tornado Warning)
# PSSCCC: County FIPS codes (can be multiple separated by '-')
# +TTTT: Duration in hours (HHMM)
# -JJJHHMM: Issue time (Julian day, Hour, Minute in UTC)
# -LLLLLLLL-: Station call sign
SAME_PATTERN = re.compile(
    r"ZCZC-(?P<org>[A-Z]{3})-(?P<event>[A-Z]{3})-"
    r"(?P<fips>([0-9]{6}-?)+)\+(?P<duration>[0-9]{4})-"
    r"(?P<issue>[0-9]{7})-(?P<callsign>[A-Z0-9/]{8})-"
)


@dataclass
class SAMEAlert:
    originator: str
    event_code: str
    event_name: str
    fips_codes: List[str]
    duration_minutes: int
    issued_at: datetime
    call_sign: str
    ui_level: str
    source: str = "same_rf"


def _classify_same_event(event_code: str) -> str:
    """Map event code to ui_level based on config."""
    cfg = get_config()
    event_name = SAME_EVENT_CODES.get(event_code, "Unknown Event")
    
    if event_name in cfg.alert_classification.get("critical_events", []):
        return "critical"
    if event_name in cfg.alert_classification.get("high_events", []):
        return "high"
    if event_name in cfg.alert_classification.get("moderate_events", []):
        return "moderate"
    return "info"


def _passes_fips_filter(fips_codes: List[str]) -> bool:
    """Check if any of the alert's FIPS codes match our configured filter."""
    cfg = get_config()
    same_cfg = cfg.noaa_weather_radio.get("same_decoder", {})
    
    if same_cfg.get("accept_all_areas", False):
        return True
        
    filter_list = same_cfg.get("fips_filter", [])
    if not filter_list:
        return True  # If no filter specified, accept all
        
    for fips in fips_codes:
        if fips in filter_list:
            return True
    return False


def _parse_same_duration(duration_str: str) -> int:
    """Parse +TTTT into minutes."""
    try:
        hours = int(duration_str[:2])
        minutes = int(duration_str[2:])
        return (hours * 60) + minutes
    except ValueError:
        return 0


def _parse_same_issue_time(issue_str: str) -> datetime:
    """Parse JJJHHMM into UTC datetime for the current year."""
    try:
        now = datetime.now(timezone.utc)
        year = now.year
        julian_day = int(issue_str[:3])
        hour = int(issue_str[3:5])
        minute = int(issue_str[5:7])
        
        # Create datetime for start of year, then add (Julian day - 1)
        issue_time = datetime(year, 1, 1, tzinfo=timezone.utc) + \
                     timedelta(days=julian_day - 1, hours=hour, minutes=minute)
                     
        # Handle end-of-year edge case (e.g. alert issued Dec 31, parsed Jan 1)
        if issue_time > now + timedelta(days=2):
            # Probably from late last year
            issue_time = datetime(year - 1, 1, 1, tzinfo=timezone.utc) + \
                         timedelta(days=julian_day - 1, hours=hour, minutes=minute)
            
        return issue_time
    except ValueError:
        return datetime.now(timezone.utc)


def parse_same_string(same_str: str) -> Optional[SAMEAlert]:
    """
    Parse a raw SAME header string into a SAMEAlert object.
    
    Args:
        same_str: Raw SAME string e.g. 'ZCZC-WXR-TOR-017031+0030-1921523-KLOT/NWS-'
        
    Returns:
        SAMEAlert object or None if parse fails or filtered.
    """
    match = SAME_PATTERN.search(same_str)
    if not match:
        return None
        
    groups = match.groupdict()
    fips_str = groups["fips"]
    
    # FIPS block is like "017031-017032-", we split by '-' and remove empties
    fips_codes = [f for f in fips_str.split("-") if f]
    
    if not _passes_fips_filter(fips_codes):
        logger.debug(f"SAME alert {groups['event']} rejected by FIPS filter")
        return None
        
    event_code = groups["event"]
    ui_level = _classify_same_event(event_code)
    
    alert = SAMEAlert(
        originator=groups["org"],
        event_code=event_code,
        event_name=SAME_EVENT_CODES.get(event_code, f"Unknown ({event_code})"),
        fips_codes=fips_codes,
        duration_minutes=_parse_same_duration(groups["duration"]),
        issued_at=_parse_same_issue_time(groups["issue"]),
        call_sign=groups["callsign"],
        ui_level=ui_level
    )
    
    return alert


def decode_same_from_wav(wav_path: Path | str) -> List[SAMEAlert]:
    """
    Decode SAME signals from a WAV file using multimon-ng.
    
    Args:
        wav_path: Path to the WAV file.
        
    Returns:
        List of parsed SAMEAlerts.
    """
    wav_path = Path(wav_path)
    if not wav_path.exists():
        logger.error(f"WAV file not found: {wav_path}")
        return []
        
    cmd = ["multimon-ng", "-t", "wav", "-a", "EAS", str(wav_path)]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        alerts = []
        for line in result.stdout.splitlines():
            if line.startswith("EAS:"):
                alert = parse_same_string(line)
                if alert:
                    alerts.append(alert)
                    
        return alerts
        
    except FileNotFoundError:
        logger.error("multimon-ng not found. Install it via scripts/install_deps.sh")
        return []
    except subprocess.TimeoutExpired:
        logger.error("multimon-ng timed out parsing WAV")
        return []
