# 🛰️ pi_noaa — Weather Satellite Receiving Station
## Comprehensive Project Build Prompt — v2 (Revised)

> **Revision notes:** This version corrects the offline/mode architecture, clarifies why
> satellite parameters live in config.yaml, adds a true RF-based NOAA Weather Radio
> receiver for genuine offline alert capability, and introduces TLE staleness handling
> and a local SQLite cache for degraded-connectivity operation.

---

## 🎯 Project Vision

Build **pi_noaa**: a full-stack Python application that receives, decodes, and visualizes
real-time weather data from orbiting NOAA APT satellites using an RTL-SDR USB dongle.
The system has a **three-source alert pipeline** — always trying the best available source:

1. **NWS API** (online, richest data) — polls `api.weather.gov` for structured alerts
2. **NOAA Weather Radio RF** (offline-capable) — tunes the same RTL-SDR to 162 MHz
   and decodes SAME-coded alert broadcasts directly from ground transmitters
3. **SQLite local cache** (last resort) — serves stale-but-valid cached data with a
   clear UI banner when fully disconnected

A rich **web dashboard** (served from the Pi) displays decoded satellite imagery, orbital
passes, live weather alerts (tornado, hail, flash flood, etc.), and system diagnostics —
all configurable via a single `config.yaml`.

---

## ❓ Why Are Satellites Configured in config.yaml?

This is an important architectural question. The satellite entries serve **two separate
purposes** with very different internet dependencies:

### 1 — RF Frequencies (Zero Internet Required)
```yaml
frequency_hz: 137620000   # NOAA 15 always broadcasts APT here — this never changes
```
The SDR hardware needs to know which frequency to tune to. These are internationally
published, fixed allocations. The system reads them from config at startup to tune the
radio — **no internet whatsoever**.

### 2 — NORAD IDs (Internet Required, but Gracefully Cached)
```yaml
norad_id: 25338           # Used to look up TLE orbital data from Celestrak
```
NORAD IDs identify which satellite's TLE (Two-Line Element) to download. TLEs are
the mathematical orbital parameters used to predict *when* and *where* a satellite
will pass overhead. They change slightly every day as orbits decay.

**Key design decision:** TLEs are cached locally. The system continues predicting passes
using stale TLEs for up to 72 hours (configurable), with accuracy degrading gracefully.
The UI shows a warning banner when TLE data is stale.

---

## 🗺️ Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                              pi_noaa                                 │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    RTL-SDR Hardware                          │   │
│  │                                                              │   │
│  │   TIME-SHARED between two listening modes:                   │   │
│  │                                                              │   │
│  │  ┌───────────────────────┐   ┌──────────────────────────┐   │   │
│  │  │  MODE A: 137.x MHz    │   │  MODE B: 162.x MHz       │   │   │
│  │  │  APT Satellite Passes │   │  NOAA Weather Radio RF   │   │   │
│  │  │  (scheduled windows)  │   │  (between/without passes)│   │   │
│  │  └──────────┬────────────┘   └───────────┬──────────────┘   │   │
│  └─────────────┼──────────────────────────── ┼──────────────────┘   │
│                │                             │                      │
│         ┌──────▼──────┐             ┌────────▼──────────┐          │
│         │ APT Decoder │             │  SAME Decoder      │          │
│         │ (aptdec)    │             │  (same_decoder.py) │          │
│         └──────┬──────┘             └────────┬──────────┘          │
│                │                             │                      │
│  ┌─────────────▼─────────────────────────────▼──────────────────┐  │
│  │                    Alert Pipeline                             │  │
│  │                                                               │  │
│  │  Source 1: NWS API (online)  ──────────────────────────────┐ │  │
│  │  Source 2: SAME RF Decode (offline) ────────────────────── ▼ │  │
│  │  Source 3: SQLite Cache (degraded) ─────────► AlertMerger   │ │  │
│  │                                                    │         │ │  │
│  └────────────────────────────────────────────────────┼─────────┘  │
│                                                        │            │
│  ┌─────────────┐   ┌─────────────┐    ┌───────────────▼──────────┐ │
│  │ TLE Fetcher │   │Pass Predictor│   │  FastAPI + Socket.IO     │ │
│  │ (cached,    │──▶│(pyorbital)  │──▶│  Server                  │ │
│  │  stale-ok)  │   └─────────────┘   └───────────────┬──────────┘ │
│  └─────────────┘                                      │            │
│                                          ┌────────────▼──────────┐ │
│                                          │  Web Dashboard (UI)   │ │
│                                          │  HTML/CSS/JS + WS     │ │
│                                          └───────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Operating Mode Decision Tree

The system auto-detects connectivity and hardware at startup, then re-evaluates
every `mode.recheck_interval_minutes` minutes:

```
startup / periodic recheck
        │
        ├─ SDR hardware detected?
        │       │
        │       ├─ YES ──► Internet reachable?
        │       │               ├─ YES ──► MODE: "dual"
        │       │               │          SDR (137 MHz satellite) +
        │       │               │          NWS API alerts +
        │       │               │          162 MHz WX Radio (between passes)
        │       │               │
        │       │               └─ NO  ──► MODE: "sdr_offline"
        │       │                          SDR (137 MHz satellite) +
        │       │                          162 MHz WX Radio SAME decode +
        │       │                          Stale TLEs (if cache fresh enough)
        │       │
        └─ NO  ──► Internet reachable?
                        ├─ YES ──► MODE: "api_only"
                        │          NWS API alerts only
                        │          No satellite imagery
                        │
                        └─ NO  ──► MODE: "degraded"
                                   SQLite cached alerts (stamped stale)
                                   Last satellite image shown (stamped stale)
                                   UI shows full offline warning banner
```

**Alert source priority (highest wins, merged deduplicated):**
```
NWS API (richest, structured) > SAME RF decode > SQLite cache
```

---

## 📦 Project Scaffold

```
pi_noaa/
│
├── config.yaml                     # ← Single source of truth for ALL parameters
├── requirements.txt
├── README.md
│
├── main.py                         # Application entry point + mode resolver
│
├── core/
│   ├── __init__.py
│   ├── config_loader.py            # Loads & validates config.yaml (Pydantic)
│   ├── scheduler.py                # APScheduler job orchestrator
│   ├── mode_resolver.py            # Detects hardware/internet, resolves active mode
│   ├── connectivity.py             # Internet reachability probe (offline detection)
│   └── logger.py                   # Centralized structured logging
│
├── sdr/
│   ├── __init__.py
│   ├── sdr_controller.py           # RTL-SDR device management; time-shares the dongle
│   ├── signal_recorder.py          # Records IQ samples / raw audio to WAV
│   ├── apt_decoder.py              # Decodes APT 137 MHz → raw image (aptdec wrapper)
│   └── image_processor.py         # Enhance, colorize, geo-overlay satellite image
│
├── wx_radio/                       # NEW — True offline 162 MHz NOAA Weather Radio
│   ├── __init__.py
│   ├── wx_radio_receiver.py        # rtl_fm tuned to 162 MHz, records audio
│   ├── same_decoder.py             # Parses SAME digital alert headers from audio
│   ├── same_codes.py               # SAME event code → human label + severity map
│   └── frequency_scanner.py       # Scans all 7 WX freqs, picks strongest signal
│
├── orbital/
│   ├── __init__.py
│   ├── tle_fetcher.py              # Downloads & caches TLE data (Celestrak)
│   ├── tle_staleness.py            # NEW — checks TLE age, warns, degrades gracefully
│   ├── pass_predictor.py           # Predicts satellite passes (pyorbital)
│   └── satellite_tracker.py        # Real-time az/el tracking during pass
│
├── alerts/
│   ├── __init__.py
│   ├── nws_client.py               # NWS API (api.weather.gov) client — online source
│   ├── nws_alert_monitor.py        # Polls & parses NWS alerts; fires callbacks
│   ├── same_alert_monitor.py       # Wraps same_decoder into alert stream
│   ├── alert_merger.py             # Deduplicates alerts from all sources
│   ├── alert_classifier.py         # Assigns ui_level + color from config rules
│   └── cache_store.py              # NEW — SQLite-backed alert & image cache
│
├── api/
│   ├── __init__.py
│   ├── server.py                   # FastAPI app + Socket.IO + lifespan tasks
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── passes.py               # GET /api/passes
│   │   ├── images.py               # GET /api/images
│   │   ├── alerts.py               # GET /api/alerts
│   │   ├── status.py               # GET /api/status  (mode, connectivity, TLE age)
│   │   └── config_view.py          # GET /api/config  (sanitized read-only view)
│   └── websocket.py                # Socket.IO events for real-time push
│
├── ui/
│   ├── templates/
│   │   └── index.html              # Single-page dashboard
│   └── static/
│       ├── css/
│       │   └── dashboard.css
│       ├── js/
│       │   ├── dashboard.js
│       │   ├── alert_banner.js     # Severe weather alert overlay + audio chime
│       │   ├── offline_banner.js   # NEW — stale data / offline warning UI
│       │   ├── pass_clock.js       # Countdown to next pass
│       │   └── satellite_map.js   # Live sky view (az/el polar plot)
│       └── assets/
│           └── satellite_icons/
│
├── data/
│   ├── tle_cache/                  # Cached TLE files (with timestamp)
│   ├── recordings/                 # Raw WAV recordings (satellite + WX radio)
│   ├── images/                     # Decoded & processed satellite images
│   ├── alerts/                     # Archived alert JSONs (from all sources)
│   └── pi_noaa.db                  # SQLite database (alerts cache, pass log)
│
├── scripts/
│   ├── install_deps.sh             # One-shot dependency installer
│   ├── setup_rtlsdr.sh             # RTL-SDR udev rules & blacklist
│   ├── scan_wx_radio.py            # Utility: find strongest WX Radio frequency
│   └── test_sdr.py                 # Hardware sanity check
│
└── tests/
    ├── test_config_loader.py
    ├── test_pass_predictor.py
    ├── test_tle_staleness.py
    ├── test_apt_decoder.py
    ├── test_same_decoder.py
    ├── test_alert_merger.py
    └── test_nws_alert_monitor.py
```

---

## ⚙️ config.yaml — Fully Externalized Configuration

```yaml
# ============================================================
#  pi_noaa Configuration File — v2
#  All tuneable parameters live here. No hardcoding in code.
#
#  ABOUT SATELLITE ENTRIES:
#    frequency_hz  → SDR tuning param. Does NOT need internet.
#                    These are fixed ITU allocations that never change.
#    norad_id      → Used to fetch TLEs from Celestrak (needs internet).
#                    TLEs are cached; system works offline with stale cache.
# ============================================================

# ─── Observer Location ───────────────────────────────────────
location:
  name: "Home Station"
  latitude: 41.8827         # Decimal degrees, North positive
  longitude: -87.6233       # Decimal degrees, East positive
  altitude_m: 182           # Meters above sea level

# ─── Operating Mode ──────────────────────────────────────────
mode:
  # "auto"       — Detect hardware & internet, choose best mode (recommended)
  # "dual"       — Force SDR + NWS API (assume both available)
  # "sdr_offline"— Force SDR + 162MHz WX Radio (no internet assumed)
  # "api_only"   — Force NWS API alerts only (no SDR hardware)
  # "degraded"   — Force cached data only (testing/demo)
  primary: "auto"
  # How often (minutes) to recheck hardware/internet and potentially switch mode
  recheck_interval_minutes: 10
  # Time before a satellite pass (minutes) to arm the SDR receiver
  sdr_arm_minutes_before: 5
  # Whether to automatically switch to 162MHz WX Radio between satellite passes
  wx_radio_between_passes: true

# ─── SDR Hardware ────────────────────────────────────────────
sdr:
  device_index: 0           # RTL-SDR device index (0 = first dongle)
  sample_rate_hz: 2400000   # 2.4 MSPS — good for APT satellite reception
  ppm_correction: 0         # Frequency error correction (run: rtl_test -p)
  gain_mode: "auto"         # "auto" or "manual"
  gain_db: 49.6             # Only used when gain_mode is "manual"
  bias_tee: false           # Enable if using a powered LNA inline

# ─── Satellite Targets ───────────────────────────────────────
# frequency_hz: SDR hardware tuning — does NOT require internet
# norad_id:     TLE lookup identity — requires internet (cached offline)
satellites:
  - name: "NOAA 15"
    norad_id: 25338
    frequency_hz: 137620000   # 137.620 MHz — fixed ITU allocation
    signal_type: "APT"
    enabled: true
    min_elevation_deg: 10     # Ignore passes below this elevation (horizon clutter)

  - name: "NOAA 18"
    norad_id: 28654
    frequency_hz: 137912500   # 137.9125 MHz
    signal_type: "APT"
    enabled: true
    min_elevation_deg: 10

  - name: "NOAA 19"
    norad_id: 33591
    frequency_hz: 137100000   # 137.100 MHz
    signal_type: "APT"
    enabled: true
    min_elevation_deg: 10

  - name: "Meteor-M2 3"
    norad_id: 57166
    frequency_hz: 137900000   # 137.900 MHz
    signal_type: "LRPT"
    enabled: false            # Requires different decoder (meteor-demod + medet)
    min_elevation_deg: 15

# ─── TLE / Orbital Data ──────────────────────────────────────
tle:
  weather_tle_url: "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle"
  cache_dir: "data/tle_cache"
  tle_filename: "weather.tle"
  # Normal refresh interval (when online)
  cache_ttl_hours: 6
  # OFFLINE BEHAVIOUR: How old TLEs can be before the system refuses to predict
  # TLEs remain usable for ~2-3 days with minor accuracy loss
  stale_tle_max_age_hours: 72
  # Show a UI warning once TLE age exceeds this (even if still usable)
  warn_if_stale_after_hours: 24
  # If TLE is too old AND internet is unavailable, fall back to last known passes
  # from SQLite cache rather than predicting nothing
  fallback_to_cached_passes: true

# ─── Pass Prediction ─────────────────────────────────────────
pass_prediction:
  lookahead_hours: 24
  max_passes_displayed: 10
  scheduler_interval_minutes: 60

# ─── Signal Recording & Decoding ─────────────────────────────
recording:
  output_dir: "data/recordings"
  format: "wav"
  sample_rate_hz: 48000
  max_recording_minutes: 20
  keep_raw_recordings: false

apt_decoder:
  # "aptdec" (recommended, open source), "wxtoimg" (legacy, requires license)
  backend: "aptdec"
  aptdec_path: "/usr/local/bin/aptdec"
  output_dir: "data/images"
  image_format: "png"
  enhancements:
    - "ZA"                   # NOAA standard color enhancement table
  add_map_overlay: true
  add_telemetry_strip: true
  add_timestamp_watermark: true

# ─── Image Enhancement ───────────────────────────────────────
image:
  output_dir: "data/images"
  thumbnail_size: [320, 240]
  max_images_stored: 50
  colormap: "thermal"        # "thermal" | "grey" | "rainbow" | "contrast"
  auto_rotate: true

# ─── NOAA Weather Radio — 162 MHz RF (TRUE OFFLINE ALERTS) ──
# This tunes the RTL-SDR to 162 MHz NOAA Weather Radio ground transmitters.
# Works with ZERO internet. Decodes embedded SAME alert codes from audio.
# The SDR is time-shared: 162 MHz when not recording a satellite pass.
noaa_weather_radio:
  enabled: true
  # Standard 7 NOAA Weather Radio frequencies (MHz)
  frequencies_hz:
    - 162400000   # WX1
    - 162425000   # WX2
    - 162450000   # WX3
    - 162475000   # WX4
    - 162500000   # WX5
    - 162525000   # WX6
    - 162550000   # WX7
  # Auto-scan all freqs on startup and pick strongest signal
  auto_scan_on_start: true
  # Override to lock to a specific frequency (set null for auto)
  preferred_frequency_hz: null
  # How long (seconds) to listen on each frequency during scan
  scan_dwell_seconds: 5
  # SAME decoder settings
  same_decoder:
    enabled: true
    # Your county FIPS code(s) for SAME filtering (empty = accept all)
    # Find yours at: https://www.nws.noaa.gov/nwr/coverage/county_coverage.html
    fips_filter:
      - "017031"             # Example: Cook County, IL
    # Accept alerts for all counties (ignore fips_filter)
    accept_all_areas: false
  # Record WX Radio audio clips when a SAME alert is detected
  record_alert_audio: true
  alert_audio_dir: "data/recordings/wx_alerts"
  # Continuously record WX Radio audio (large disk usage)
  continuous_record: false

# ─── NWS API Alerts (Online Only) ───────────────────────────
nws_api:
  base_url: "https://api.weather.gov"
  # Your NWS zone/county code — find at https://alerts.weather.gov
  alert_zone: "ILC031"       # Example: Cook County, IL
  alert_state: "IL"
  poll_interval_seconds: 60
  request_timeout_seconds: 15
  # User-Agent required by NWS API fair-use policy
  user_agent: "pi_noaa/2.0 (your@email.com)"

# ─── Alert Classification ─────────────────────────────────────
# Used by alert_classifier.py for ALL alert sources (NWS API + SAME RF)
alert_classification:
  severity_filter:
    - "Extreme"
    - "Severe"
    - "Moderate"
  # ui_level → "critical" = red pulsing banner
  critical_events:
    - "Tornado Warning"
    - "Severe Thunderstorm Warning"
    - "Flash Flood Emergency"
    - "Flash Flood Warning"
    - "Blizzard Warning"
    - "Ice Storm Warning"
    - "Extreme Wind Warning"
    - "Special Marine Warning"
    - "Dust Storm Warning"
    - "Tsunami Warning"
  # ui_level → "high" = orange banner
  high_events:
    - "Hail Warning"
    - "Flood Warning"
    - "Winter Storm Warning"
    - "Dense Fog Advisory"
    - "Freeze Warning"
    - "High Wind Warning"
    - "Avalanche Warning"
  # ui_level → "moderate" = yellow banner
  moderate_events:
    - "Flood Watch"
    - "Flash Flood Watch"
    - "Tornado Watch"
    - "Severe Thunderstorm Watch"
    - "Winter Storm Watch"
    - "Frost Advisory"
    - "Wind Advisory"

# ─── Local Cache (SQLite — Offline Fallback) ────────────────
offline_cache:
  db_path: "data/pi_noaa.db"
  # Max alerts to keep in SQLite (rolling window)
  max_cached_alerts: 200
  # Max age of a cached alert before it's hidden from UI even offline
  max_stale_alert_age_hours: 48
  # Cache the last N decoded satellite images' metadata for offline display
  cached_image_metadata_count: 20
  # Store last pass predictions for offline display
  cached_passes_count: 50
  # Show a banner in UI when serving from cache
  show_stale_banner: true

# ─── Connectivity Probe ──────────────────────────────────────
connectivity:
  # Host to probe to check internet (DNS lookup + TCP)
  probe_host: "api.weather.gov"
  probe_port: 443
  probe_timeout_seconds: 5
  # Also try a fallback host
  probe_fallback_host: "1.1.1.1"

# ─── Web Server ──────────────────────────────────────────────
server:
  host: "0.0.0.0"
  port: 5000
  debug: false
  secret_key: "CHANGE_ME_IN_PRODUCTION_USE_STRONG_RANDOM_KEY"
  cors_origins:
    - "http://localhost:5000"
    - "http://pi_noaa.local:5000"
  auth_enabled: false
  auth_username: "admin"
  auth_password: "changeme"

# ─── WebSocket Push ──────────────────────────────────────────
websocket:
  pass_update_interval_seconds: 5
  alert_push_on_new: true
  system_status_interval_seconds: 30

# ─── Storage & Retention ─────────────────────────────────────
storage:
  data_root: "data"
  max_disk_usage_gb: 10
  image_retention_days: 30
  alert_retention_days: 90
  recording_retention_days: 7

# ─── Logging ─────────────────────────────────────────────────
logging:
  level: "INFO"              # DEBUG | INFO | WARNING | ERROR
  log_dir: "logs"
  log_filename: "pi_noaa.log"
  max_bytes: 10485760        # 10 MB
  backup_count: 5
  json_format: false

# ─── Notifications (optional) ────────────────────────────────
notifications:
  enabled: false
  ntfy:
    enabled: false
    server: "https://ntfy.sh"
    topic: "pi_noaa_alerts"
    min_severity: "Severe"
  email:
    enabled: false
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    username: "your@email.com"
    password: "your_app_password"
    to_address: "your@email.com"
```

---

## 🐍 Key Python Module Details

### `core/connectivity.py`
```python
"""
Probes internet reachability with a TCP connection to a known host.
Used by mode_resolver to determine online/offline state.
All probe parameters are read from config.
"""
import socket
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)

def is_internet_available() -> bool:
    """
    Attempts TCP connection to configured probe host.
    Falls back to a secondary host if primary fails.
    Returns True if either succeeds.
    """
    cfg = get_config().connectivity
    hosts = [
        (cfg["probe_host"], cfg["probe_port"]),
        (cfg["probe_fallback_host"], 53),
    ]
    timeout = cfg["probe_timeout_seconds"]

    for host, port in hosts:
        try:
            socket.setdefaulttimeout(timeout)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
            logger.debug(f"Internet probe OK via {host}:{port}")
            return True
        except OSError:
            logger.debug(f"Internet probe failed via {host}:{port}")
            continue
    return False
```

---

### `core/mode_resolver.py`
```python
"""
Determines the effective operating mode based on hardware availability
and internet reachability. Re-evaluates periodically per config.
Emits mode change events to WebSocket clients.
"""
from enum import Enum
from core.config_loader import get_config
from core.connectivity import is_internet_available
from sdr.sdr_controller import SDRController
from core.logger import get_logger

logger = get_logger(__name__)

class OperatingMode(str, Enum):
    DUAL        = "dual"         # SDR satellite + NWS API (both available)
    SDR_OFFLINE = "sdr_offline"  # SDR satellite + 162MHz WX Radio (no internet)
    API_ONLY    = "api_only"     # NWS API alerts only (no SDR hardware)
    DEGRADED    = "degraded"     # SQLite cache only (no hardware, no internet)

_current_mode: OperatingMode | None = None
_mode_change_callbacks = []

def resolve_mode() -> OperatingMode:
    """
    Runs the decision tree and returns the effective OperatingMode.
    Also fires callbacks if mode changed since last call.
    """
    global _current_mode
    cfg = get_config()
    forced = cfg.mode["primary"]

    if forced != "auto":
        mode = OperatingMode(forced)
    else:
        sdr = SDRController()
        has_hardware = sdr.is_hardware_present()
        has_internet = is_internet_available()

        if has_hardware and has_internet:
            mode = OperatingMode.DUAL
        elif has_hardware and not has_internet:
            mode = OperatingMode.SDR_OFFLINE
        elif not has_hardware and has_internet:
            mode = OperatingMode.API_ONLY
        else:
            mode = OperatingMode.DEGRADED

    if mode != _current_mode:
        logger.info(f"Operating mode: {_current_mode} → {mode}")
        _current_mode = mode
        for cb in _mode_change_callbacks:
            cb(mode)

    return mode

def on_mode_change(callback):
    """Register a callback fired when operating mode changes."""
    _mode_change_callbacks.append(callback)
```

---

### `orbital/tle_staleness.py`
```python
"""
Checks TLE cache age and provides staleness warnings.
Allows the system to continue predicting with stale TLEs rather than failing.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)

def get_tle_age_hours() -> float | None:
    """Returns age of cached TLE file in hours, or None if no cache exists."""
    cfg = get_config().tle
    tle_path = Path(cfg["cache_dir"]) / cfg["tle_filename"]
    if not tle_path.exists():
        return None
    mtime = datetime.fromtimestamp(tle_path.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - mtime).total_seconds() / 3600

def tle_is_usable() -> tuple[bool, str]:
    """
    Returns (is_usable, reason_string).
    Usable = exists and younger than stale_tle_max_age_hours.
    """
    cfg = get_config().tle
    age = get_tle_age_hours()

    if age is None:
        return False, "No TLE cache found — internet required for first run"

    max_age = cfg["stale_tle_max_age_hours"]
    warn_age = cfg["warn_if_stale_after_hours"]

    if age > max_age:
        return False, f"TLE data is {age:.0f}h old (max allowed: {max_age}h)"
    elif age > warn_age:
        return True, f"WARNING: TLE data is {age:.0f}h old — pass predictions may drift slightly"
    return True, "TLE data is fresh"

def tle_staleness_banner() -> dict | None:
    """
    Returns a UI banner dict if TLE data warrants user notification.
    Returns None if everything is fine.
    """
    usable, reason = tle_is_usable()
    if not usable:
        return {"level": "error", "message": f"⚠ {reason}. Showing cached pass schedule."}
    cfg = get_config().tle
    age = get_tle_age_hours()
    if age and age > cfg["warn_if_stale_after_hours"]:
        return {"level": "warning", "message": f"🕐 {reason}"}
    return None
```

---

### `wx_radio/same_decoder.py`
```python
"""
Decodes SAME (Specific Area Message Encoding) alert headers
from NOAA Weather Radio audio recorded via the RTL-SDR at 162 MHz.

SAME alerts are embedded as 1050 Hz FSK tones. This module uses
multimon-ng (system binary) to decode them from WAV audio,
then parses the structured SAME string into a WeatherAlert object.

No internet required — this is pure RF-to-alert decoding.
"""
import subprocess
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from wx_radio.same_codes import SAME_EVENT_CODES
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)

# SAME message format:
# ZCZC-ORG-EEE-PSSCCC+TTTT-JJJHHMM-LLLLLLLL-
SAME_PATTERN = re.compile(
    r"ZCZC-(\w{3})-(\w{3})-([\d\-]+)\+(\d{4})-(\d{7})-(\w+)-"
)

@dataclass
class SAMEAlert:
    originator: str          # WXR = NWS, EAS = EAS participant, etc.
    event_code: str          # 3-char code e.g. "TOR", "FFW", "SVR"
    event_name: str          # Human-readable e.g. "Tornado Warning"
    fips_codes: list[str]    # Affected county FIPS codes
    duration_minutes: int
    issued_at: datetime
    call_sign: str           # Issuing station
    ui_level: str            # "critical" | "high" | "moderate" | "info"
    source: str = "same_rf"  # Always "same_rf" for traceability

def decode_same_from_wav(wav_path: str) -> list[SAMEAlert]:
    """
    Run multimon-ng on a WAV file to extract SAME strings,
    then parse each into SAMEAlert objects.
    """
    try:
        result = subprocess.run(
            ["multimon-ng", "-t", "wav", "-a", "EAS", wav_path],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.error(f"multimon-ng failed: {e}")
        return []

    alerts = []
    for match in SAME_PATTERN.finditer(output):
        originator, event_code, fips_str, duration_str, time_str, call_sign = match.groups()
        fips_codes = fips_str.split("-")
        duration_minutes = int(duration_str[:2]) * 60 + int(duration_str[2:])
        # Parse issue time (Julian day + HHMM UTC)
        day_of_year = int(time_str[:3])
        hour = int(time_str[3:5])
        minute = int(time_str[5:7])
        now = datetime.now(timezone.utc)
        issued_at = datetime(now.year, 1, 1, hour, minute, tzinfo=timezone.utc) \
                    + timedelta(days=day_of_year - 1)

        event_name = SAME_EVENT_CODES.get(event_code, f"Unknown ({event_code})")
        ui_level = _classify_same_event(event_code)

        alert = SAMEAlert(
            originator=originator,
            event_code=event_code,
            event_name=event_name,
            fips_codes=fips_codes,
            duration_minutes=duration_minutes,
            issued_at=issued_at,
            call_sign=call_sign,
            ui_level=ui_level,
        )

        # Apply FIPS filter from config
        if _passes_fips_filter(fips_codes):
            alerts.append(alert)
            logger.info(f"SAME alert decoded: {event_name} ({event_code}) — {fips_codes}")

    return alerts

def _classify_same_event(event_code: str) -> str:
    # Critical SAME codes
    critical = {"TOR", "SVR", "FFE", "FFW", "BZW", "ICE", "EWW", "SMW", "DSW"}
    high     = {"FLW", "WSW", "DFO", "FRW", "HWW", "AVW"}
    moderate = {"FFA", "FFA", "TOA", "SVA", "WSA"}
    if event_code in critical: return "critical"
    if event_code in high:     return "high"
    if event_code in moderate: return "moderate"
    return "info"

def _passes_fips_filter(fips_codes: list[str]) -> bool:
    cfg = get_config().noaa_weather_radio["same_decoder"]
    if cfg["accept_all_areas"]:
        return True
    filter_codes = cfg.get("fips_filter", [])
    if not filter_codes:
        return True
    return any(f in filter_codes for f in fips_codes)
```

---

### `wx_radio/same_codes.py`
```python
"""
SAME event code → human-readable name mapping.
Source: NOAA NWR SAME specification.
All offline — no internet needed.
"""
SAME_EVENT_CODES = {
    # Warnings (most severe)
    "TOR": "Tornado Warning",
    "SVR": "Severe Thunderstorm Warning",
    "FFW": "Flash Flood Warning",
    "FFE": "Flash Flood Emergency",
    "FLW": "Flood Warning",
    "SMW": "Special Marine Warning",
    "HWW": "High Wind Warning",
    "BZW": "Blizzard Warning",
    "WSW": "Winter Storm Warning",
    "ICE": "Ice Storm Warning",
    "EWW": "Extreme Wind Warning",
    "DSW": "Dust Storm Warning",
    "AVW": "Avalanche Warning",
    "EAN": "Emergency Action Notification",  # Presidential / FEMA
    "NIC": "National Information Center",
    # Watches
    "TOA": "Tornado Watch",
    "SVA": "Severe Thunderstorm Watch",
    "FFA": "Flash Flood Watch",
    "FLA": "Flood Watch",
    "WSA": "Winter Storm Watch",
    "HWA": "High Wind Watch",
    # Advisories
    "DGL": "Dense Fog Advisory",
    "FRW": "Freeze Warning",
    "FRA": "Frost Advisory",
    "WND": "Wind Advisory",
    # Statements
    "FFS": "Flash Flood Statement",
    "FLS": "Flood Statement",
    "SVS": "Severe Weather Statement",
    "SPS": "Special Weather Statement",
    # Tests
    "RWT": "Required Weekly Test",
    "RMT": "Required Monthly Test",
}
```

---

### `alerts/alert_merger.py`
```python
"""
Merges alerts from all three sources (NWS API, SAME RF, SQLite cache)
into a single deduplicated list, ordered by severity then recency.
Source priority: nws_api > same_rf > cache
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List
from core.logger import get_logger

logger = get_logger(__name__)

SOURCE_PRIORITY = {"nws_api": 1, "same_rf": 2, "cache": 3}

@dataclass
class UnifiedAlert:
    id: str
    event: str
    headline: str
    description: str
    severity: str
    ui_level: str       # "critical" | "high" | "moderate" | "info"
    color: str
    effective: datetime
    expires: datetime
    area_desc: str
    source: str         # "nws_api" | "same_rf" | "cache"
    is_stale: bool = False

def merge_alerts(
    nws_alerts: list,
    same_alerts: list,
    cached_alerts: list,
    internet_available: bool
) -> List[UnifiedAlert]:
    """
    Merge and deduplicate alerts from all sources.
    - If internet available: NWS API alerts are authoritative
    - SAME RF alerts supplement with anything not already in NWS list
    - Cache alerts only used if no live source has data
    """
    seen_events: set[str] = set()
    result: List[UnifiedAlert] = []

    # Priority 1: NWS API (richest, most structured)
    if internet_available:
        for a in nws_alerts:
            key = f"{a.event}:{a.area_desc}"
            if key not in seen_events:
                seen_events.add(key)
                result.append(_to_unified(a, "nws_api"))

    # Priority 2: SAME RF (offline-capable supplement)
    for a in same_alerts:
        key = f"{a.event_name}:{','.join(a.fips_codes)}"
        if key not in seen_events:
            seen_events.add(key)
            result.append(_to_unified_same(a))

    # Priority 3: Cache (only if no live data at all)
    if not result:
        for a in cached_alerts:
            result.append(_to_unified(a, "cache", is_stale=True))

    # Sort: critical first, then by recency
    level_order = {"critical": 0, "high": 1, "moderate": 2, "info": 3}
    result.sort(key=lambda a: (level_order.get(a.ui_level, 9), a.effective), reverse=False)
    return result
```

---

### `alerts/cache_store.py`
```python
"""
SQLite-backed cache for alerts and pass predictions.
Enables the system to show recent data when fully offline.
Uses only Python stdlib sqlite3 — no extra dependencies.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)

def get_db() -> sqlite3.Connection:
    cfg = get_config()
    db_path = Path(cfg.offline_cache["db_path"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn

def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS alerts (
            id          TEXT PRIMARY KEY,
            event       TEXT NOT NULL,
            ui_level    TEXT NOT NULL,
            source      TEXT NOT NULL,
            effective   TEXT NOT NULL,
            expires     TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            cached_at   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS passes (
            id              TEXT PRIMARY KEY,
            satellite_name  TEXT NOT NULL,
            aos             TEXT NOT NULL,
            los             TEXT NOT NULL,
            max_elevation   REAL NOT NULL,
            payload_json    TEXT NOT NULL,
            cached_at       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS images (
            filename        TEXT PRIMARY KEY,
            satellite_name  TEXT NOT NULL,
            captured_at     TEXT NOT NULL,
            max_elevation   REAL,
            thumbnail_path  TEXT,
            cached_at       TEXT NOT NULL
        );
    """)
    conn.commit()

def save_alert(alert_data: dict):
    """Upsert an alert into the cache."""
    cfg = get_config().offline_cache
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO alerts
            (id, event, ui_level, source, effective, expires, payload_json, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert_data["id"], alert_data["event"], alert_data["ui_level"],
            alert_data.get("source", "nws_api"),
            alert_data["effective"], alert_data["expires"],
            json.dumps(alert_data), now
        ))
        # Rolling window: delete oldest beyond max count
        conn.execute(f"""
            DELETE FROM alerts WHERE id NOT IN (
                SELECT id FROM alerts ORDER BY cached_at DESC LIMIT ?
            )
        """, (cfg["max_cached_alerts"],))

def load_cached_alerts() -> list[dict]:
    """Retrieve all non-expired cached alerts."""
    cfg = get_config().offline_cache
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) -
              timedelta(hours=cfg["max_stale_alert_age_hours"])).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT payload_json FROM alerts WHERE cached_at > ? ORDER BY ui_level, effective",
            (cutoff,)
        ).fetchall()
    return [json.loads(r["payload_json"]) for r in rows]
```

---

### `core/config_loader.py`
```python
"""
Loads config.yaml using PyYAML and validates structure with Pydantic.
All modules import get_config() — never parse YAML directly elsewhere.
"""
import yaml
from pathlib import Path
from functools import lru_cache
from pydantic import BaseModel
from typing import List, Optional

CONFIG_PATH = Path("config.yaml")

class SatelliteConfig(BaseModel):
    name: str
    norad_id: int
    frequency_hz: int      # SDR hardware tuning — no internet needed
    signal_type: str
    enabled: bool
    min_elevation_deg: float

class AppConfig(BaseModel):
    location: dict
    mode: dict
    sdr: dict
    satellites: List[SatelliteConfig]
    tle: dict
    pass_prediction: dict
    recording: dict
    apt_decoder: dict
    image: dict
    noaa_weather_radio: dict   # 162 MHz RF receiver config
    nws_api: dict              # Online NWS API config (renamed from noaa_radio)
    alert_classification: dict
    offline_cache: dict
    connectivity: dict
    server: dict
    websocket: dict
    storage: dict
    logging: dict
    notifications: dict

@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    with open(CONFIG_PATH, "r") as f:
        raw = yaml.safe_load(f)
    return AppConfig(**raw)

def reload_config() -> AppConfig:
    get_config.cache_clear()
    return get_config()
```

---

### `main.py`
```python
"""
pi_noaa entry point.
Resolves operating mode, starts all subsystems, launches web server.
"""
import asyncio
import uvicorn
import argparse
from core.config_loader import get_config
from core.logger import setup_logging
from core.mode_resolver import resolve_mode, OperatingMode, on_mode_change
from orbital.tle_staleness import tle_is_usable, get_tle_age_hours

def main():
    parser = argparse.ArgumentParser(description="pi_noaa Weather Satellite Station")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--check-hardware", action="store_true")
    parser.add_argument("--check-connectivity", action="store_true")
    parser.add_argument("--scan-wx-radio", action="store_true",
                        help="Scan 162 MHz freqs and print signal strengths")
    args = parser.parse_args()

    cfg = get_config()
    setup_logging(cfg.logging)

    if args.check_hardware:
        from sdr.sdr_controller import SDRController
        present = SDRController().is_hardware_present()
        print(f"RTL-SDR hardware: {'✓ Found' if present else '✗ Not found'}")
        return

    if args.check_connectivity:
        from core.connectivity import is_internet_available
        online = is_internet_available()
        print(f"Internet: {'✓ Reachable' if online else '✗ Offline'}")
        return

    if args.scan_wx_radio:
        from wx_radio.frequency_scanner import scan_and_report
        scan_and_report()
        return

    # Resolve and print operating mode
    mode = resolve_mode()
    print(f"🛰  pi_noaa starting — mode: [{mode.value.upper()}]")

    # TLE staleness check
    usable, reason = tle_is_usable()
    if not usable:
        print(f"⚠  TLE: {reason}")
        if mode in (OperatingMode.SDR_OFFLINE, OperatingMode.DUAL):
            age = get_tle_age_hours()
            if age is None:
                print("   ✗ No TLE cache. Run with internet first to populate TLE data.")
    else:
        print(f"   TLE: {reason}")

    from api.server import build_app
    app = build_app(mode)
    uvicorn.run(app, host=cfg.server["host"], port=cfg.server["port"])

if __name__ == "__main__":
    main()
```

---

## 📋 `requirements.txt`

```
# Core
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
python-socketio>=5.11.0
pydantic>=2.7.0
PyYAML>=6.0.1
apscheduler>=3.10.4
httpx>=0.27.0

# SDR & Signal Processing
pyrtlsdr>=0.2.93
numpy>=1.26.0
scipy>=1.13.0
soundfile>=0.12.1

# Orbital Mechanics
pyorbital>=1.8.1
ephem>=4.1.5

# Image Processing
Pillow>=10.3.0
opencv-python-headless>=4.9.0

# UI Templating
jinja2>=3.1.4

# Testing
pytest>=8.2.0
pytest-asyncio>=0.23.0
respx>=0.21.0

# System binaries required (installed via install_deps.sh, NOT pip):
# - rtl-sdr        (rtl_fm, rtl_test)
# - aptdec         (APT satellite image decoder)
# - sox            (WAV conversion)
# - multimon-ng    (SAME EAS decoder from audio — KEY for offline alerts)
# - ffmpeg         (audio format conversion)
```

---

## 🔧 `scripts/install_deps.sh` (Updated)

```bash
#!/bin/bash
set -e
echo "=== pi_noaa Dependency Installer ==="

sudo apt-get update
sudo apt-get install -y \
    rtl-sdr \
    sox \
    librtlsdr-dev \
    build-essential \
    cmake \
    git \
    python3-pip \
    python3-venv \
    ffmpeg \
    multimon-ng      # ← NEW: required for SAME offline alert decoding

# Blacklist DVB-T kernel module (required for RTL-SDR)
echo "blacklist dvb_usb_rtl28xxu" | sudo tee /etc/modprobe.d/blacklist-rtl.conf

# Install aptdec (APT image decoder)
if ! command -v aptdec &> /dev/null; then
    echo "--- Building aptdec ---"
    git clone https://github.com/csete/aptdec.git /tmp/aptdec
    cd /tmp/aptdec && mkdir build && cd build
    cmake .. && make -j4
    sudo make install
    cd -
fi

# Python virtual environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=== Installation complete! ==="
echo "Next steps:"
echo "  1. Edit config.yaml (set your latitude/longitude/alert_zone)"
echo "  2. python main.py --check-hardware"
echo "  3. python main.py --check-connectivity"
echo "  4. python main.py --scan-wx-radio   (find your strongest 162MHz freq)"
echo "  5. python main.py"
```

---

## 🖥️ UI Dashboard — Feature Specification

---

### 🗺️ Panel 1 — Interactive Alert Map (Primary / Largest Panel)

This is the **hero panel** of the dashboard — a full interactive map showing where every
active alert is geographically located as a colored polygon overlay.

#### Map Library
**Leaflet.js v1.9+** — loaded from CDN when online; bundled locally as fallback.
No API key required. Fully open-source.

#### Map Tile Source & Offline Strategy

| Scenario | Tile Source | Config key |
|---|---|---|
| **Online** | OpenStreetMap CDN (`tile.openstreetmap.org`) | `map.tile_provider: "osm"` |
| **Online (alt)** | CartoDB Dark Matter (dark-themed, better contrast) | `map.tile_provider: "carto_dark"` |
| **Offline** | Local tile server (`tileserver-gl` + `.mbtiles` file on Pi) | `map.tile_provider: "local"` |
| **Degraded offline** | Static bundled SVG county/state outline (no tiles) | `map.tile_provider: "svg_fallback"` |

The `.mbtiles` file (~300–800 MB for the continental US at zoom 0–10) is downloaded
once via the setup script and served by a lightweight Python tile server on a
configurable local port. Zoom levels 0–10 cover the entire country to county-level
detail — sufficient for alert polygons without requiring street-level data.

```yaml
# ─── Map Configuration ───────────────────────────────────────
map:
  # Tile provider: "osm" | "carto_dark" | "local" | "svg_fallback"
  tile_provider: "carto_dark"           # Best contrast for dark UI theme

  # OSM / CartoDB CDN tile URL templates (used when online)
  osm_tile_url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
  carto_dark_url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"

  # Local offline tile server (tileserver-gl)
  local_tile_server_port: 8080
  local_tile_url: "http://localhost:{local_tile_server_port}/styles/basic/{z}/{x}/{y}.png"
  mbtiles_path: "data/map_tiles/us_z0-10.mbtiles"

  # Initial map view (centered on observer location by default)
  # Set to null to auto-center on observer from location config
  initial_center_lat: null
  initial_center_lon: null
  initial_zoom: 6                       # 4=full US, 6=regional, 10=metro, 12=street

  # Zoom limits
  min_zoom: 3
  max_zoom: 12                          # mbtiles only has z0-10; OSM goes to z19

  # Auto-zoom to fit all active alert polygons on page load
  auto_fit_alerts_on_load: true
  # Auto-zoom when a NEW alert arrives via WebSocket
  auto_zoom_on_new_alert: false         # Can be disruptive; off by default
  # Padding (pixels) around polygon when auto-fitting
  fit_bounds_padding: 40

  # ── Alert Polygon Overlay Styling ──────────────────────────
  # Fill opacity controls how transparent the colored alert area is.
  # 0.0 = fully transparent (invisible fill), 1.0 = fully opaque (blocks map)
  # Recommended: 0.20–0.35 for readable map + visible alert area
  alert_fill_opacity:
    critical: 0.30                      # Red — slightly more opaque for urgency
    high:     0.25
    moderate: 0.20
    info:     0.15

  # Border stroke opacity (the polygon outline)
  # Higher opacity here makes alert boundaries crisp and readable
  alert_stroke_opacity: 0.85
  alert_stroke_width_px: 2             # 2px — visible but not distracting

  # Pulse animation on critical polygons (CSS keyframe opacity oscillation)
  animate_critical_polygons: true
  animate_pulse_period_seconds: 2

  # Show a label pin at the centroid of each alert polygon
  show_alert_labels: true
  # Label shows short event name (e.g. "TORNADO WARNING")
  label_min_zoom: 5                    # Only show labels at zoom >= 5

  # Observer location marker
  show_observer_marker: true
  observer_marker_icon: "assets/icons/station_marker.svg"

  # Satellite ground track overlay during active pass
  show_satellite_ground_track: true
  ground_track_color: "#00e5ff"
  ground_track_opacity: 0.7
  ground_track_dash_pattern: "8, 4"   # dashed line
```

#### Layer Stack (Bottom → Top)

```
┌─────────────────────────────────────────────────────┐
│  Layer 5 (top): Tooltips / popups                   │  opacity: 1.0
│  Layer 4:       Alert centroid label pins           │  opacity: 0.9
│  Layer 3:       Alert polygon borders (strokes)     │  opacity: 0.85, 2px
│  Layer 2:       Alert polygon fills                 │  opacity: 0.20–0.30
│  Layer 1:       Satellite ground track line         │  opacity: 0.70
│  Layer 0 (base):Map tiles (OSM / CartoDB / local)   │  opacity: 1.0
└─────────────────────────────────────────────────────┘
```

#### Alert Polygon Colors (on map)

| Level | Fill Color | Border Color | Fill Opacity |
|---|---|---|---|
| critical | `#ef4444` (red) | `#dc2626` | 0.30 |
| high | `#f97316` (orange) | `#ea580c` | 0.25 |
| moderate | `#eab308` (yellow) | `#ca8a04` | 0.20 |
| info | `#3b82f6` (blue) | `#2563eb` | 0.15 |

#### Where Alert Polygon Geometry Comes From

- **Online (NWS API):** Each NWS alert feature includes a `geometry` field — a
  GeoJSON `Polygon` or `MultiPolygon` of the exact affected area. Leaflet renders
  this directly via `L.geoJSON(feature.geometry, styleOptions)`.

- **Offline (SAME RF):** SAME codes include county FIPS codes but no polygon geometry.
  The app bundles a static `data/geo/us_counties.geojson` file (~2 MB, sourced from
  the US Census Bureau). The FIPS codes from SAME are used to look up and highlight
  the matching county polygons from this local file — **zero internet required**.

```yaml
geo:
  # Bundled county boundary GeoJSON (US Census, simplified for performance)
  county_boundaries_path: "data/geo/us_counties_simplified.geojson"
  # Bundled state boundary GeoJSON
  state_boundaries_path: "data/geo/us_states.geojson"
  # Simplification tolerance applied to county polygons (reduces file size)
  # 0.01 = good balance of detail vs. performance on a Raspberry Pi
  simplification_tolerance: 0.01
```

#### Zoom Behavior — Full Specification

| Action | Behavior |
|---|---||
| Scroll wheel / trackpad pinch | Smooth zoom in/out (standard Leaflet) |
| Double-click map | Zoom in 1 level centered on click |
| Click alert polygon | Map flies to fit that polygon's bounds + opens detail popup |
| "Fit All Alerts" button | Zooms to bounds of all active polygons |
| "My Location" button | Flies to observer lat/lon (from config) at zoom 8 |
| New alert arrives (WebSocket) | Optional auto-zoom (configurable, off by default) |
| Keyboard `+` / `-` | Zoom in/out |
| Touch pinch-to-zoom | Enabled on mobile/tablet |

#### Map UI Controls
```
┌──────────────────────────────────────────────────────────┐
│  [+][-]           ←─ Leaflet zoom buttons (top-left)     │
│  [⌖ My Location]  ←─ Fly to observer position            │
│  [⊡ Fit Alerts]   ←─ Fit all active alert polygons       │
│  [🗺 Layers]       ←─ Toggle: alerts / ground track / OSM │
│  [⬛ Dark / ☀ Light] ←─ Switch base map tile theme       │
│                                                          │
│  Top-right legend:                                       │
│  ■ Tornado Warning  ■ Flash Flood  ■ Watch  ■ Advisory   │
└──────────────────────────────────────────────────────────┘
```

#### Alert Popup (on polygon click)
When a user clicks any alert polygon on the map, a Leaflet popup opens showing:
```
┌─────────────────────────────────────────┐
│  🔴 TORNADO WARNING                      │
│  ─────────────────────────────────────  │
│  Area:    Cook County, IL               │
│  Source:  NWS Chicago (KLOT)            │
│  Issued:  07/11 9:45 PM CDT             │
│  Expires: 07/11 10:30 PM CDT            │
│  ─────────────────────────────────────  │
│  Take shelter immediately in an         │
│  interior room on the lowest floor...   │
│                                         │
│  [Full Details ↗]  [Dismiss]            │
└─────────────────────────────────────────┘
```

#### `ui/static/js/alert_map.js` — Implementation Outline
```javascript
/**
 * alert_map.js
 * Initializes Leaflet map, manages alert polygon layers,
 * handles WebSocket updates and tile provider switching.
 * All styling params fetched from /api/config (which reads config.yaml).
 */

const MAP_CONFIG = await fetch('/api/config/map').then(r => r.json());

// Initialize Leaflet map
const map = L.map('alert-map', {
    center: [MAP_CONFIG.initial_center_lat ?? OBSERVER_LAT,
             MAP_CONFIG.initial_center_lon ?? OBSERVER_LON],
    zoom:    MAP_CONFIG.initial_zoom,
    minZoom: MAP_CONFIG.min_zoom,
    maxZoom: MAP_CONFIG.max_zoom,
    zoomControl: true,
});

// Base tile layer (provider from config)
const tileLayer = L.tileLayer(MAP_CONFIG.tile_url, {
    attribution: '© OpenStreetMap contributors',
    maxZoom: MAP_CONFIG.max_zoom,
}).addTo(map);

// Alert polygon layer group
const alertLayer = L.layerGroup().addTo(map);

// Observer position marker
if (MAP_CONFIG.show_observer_marker) {
    L.marker([OBSERVER_LAT, OBSERVER_LON], {
        icon: observerIcon,
        title: 'Your Location'
    }).addTo(map);
}

/**
 * Renders all active alerts as GeoJSON polygons.
 * Called on page load and on WebSocket 'alerts_update' event.
 */
function renderAlertPolygons(alerts) {
    alertLayer.clearLayers();
    const bounds = [];

    alerts.forEach(alert => {
        if (!alert.geometry) return;  // SAME alerts use county lookup

        const fillOpacity = MAP_CONFIG.alert_fill_opacity[alert.ui_level];
        const color = LEVEL_COLORS[alert.ui_level];

        const layer = L.geoJSON(alert.geometry, {
            style: {
                fillColor:   color,
                fillOpacity: fillOpacity,
                color:       darken(color),       // border slightly darker
                weight:      MAP_CONFIG.alert_stroke_width_px,
                opacity:     MAP_CONFIG.alert_stroke_opacity,
            }
        });

        // Popup on click
        layer.bindPopup(buildAlertPopup(alert));

        // Pulsing CSS animation for critical alerts
        if (alert.ui_level === 'critical' && MAP_CONFIG.animate_critical_polygons) {
            layer.eachLayer(l => l.getElement()?.classList.add('pulse-polygon'));
        }

        layer.addTo(alertLayer);
        bounds.push(layer.getBounds());
    });

    // Auto-fit on load
    if (MAP_CONFIG.auto_fit_alerts_on_load && bounds.length > 0) {
        const allBounds = bounds.reduce((a, b) => a.extend(b));
        map.fitBounds(allBounds, { padding: [MAP_CONFIG.fit_bounds_padding,
                                              MAP_CONFIG.fit_bounds_padding] });
    }
}

// WebSocket: push new/updated alerts in real time
socket.on('alerts_update', (alerts) => renderAlertPolygons(alerts));
socket.on('new_alert', (alert)  => {
    renderAlertPolygons(currentAlerts); // re-render full set
    if (MAP_CONFIG.auto_zoom_on_new_alert && alert.geometry) {
        map.flyToBounds(L.geoJSON(alert.geometry).getBounds(), { duration: 1.5 });
    }
});
```

---

### Panel 2 — Alert Banner (Top of Page, Full Width)
- **Scrolling ticker** of active alerts, color-coded by `ui_level`:
  - 🔴 **Pulsing red** — Tornado Warning, Severe Thunderstorm Warning (critical)
  - 🟠 **Orange** — Flash Flood Warning, Hail Warning (high)
  - 🟡 **Yellow** — Watches, Advisories (moderate)
  - 🔵 **Blue** — Statements, Outlooks (info)
- **Source badge** on each alert: `[NWS API]` | `[WX Radio RF]` | `[Cached]`
- Click on ticker item → map **flies to that alert's polygon**
- Click → expand full NWS text in a modal
- Web Audio API chime on new critical alert via WebSocket

### Panel 3 — Connectivity & Data Freshness Banner
- **Persistent top-right status indicator**: `● Online` (green) / `● Offline` (red)
- When in `sdr_offline` mode: blue banner "Satellite + WX Radio Mode (No Internet)"
- When in `degraded` mode: orange banner "⚠ Showing Cached Data — Last updated X hours ago"
- When TLE is stale: yellow banner with TLE age and accuracy note
- When map tiles fall back to local server: "🗺 Offline map tiles" note in map corner

### Panel 4 — Next Satellite Pass Countdown
- Countdown to next AOS; satellite name, frequency, max elevation
- Visual polar pass arc plot (Chart.js / D3)
- Green progress bar during active pass recording
- Satellite ground track line shown on the alert map in cyan

### Panel 5 — Latest Satellite Image Panel
- Most recent decoded APT image (or last cached image in offline mode)
- Metadata: satellite, pass time, max elevation, decode quality %, TLE freshness
- Thumbnail gallery of recent N images
- Enhancement selector (greyscale / thermal / false color)
- **"Overlay on Map" toggle** — drapes the georeferenced APT image onto the
  Leaflet map as an `L.imageOverlay` at ~0.65 opacity so the base map shows through

### Panel 6 — Active Alerts Table
- All live alerts (merged from all sources): Type | Source | Severity | Area | Expires
- Color-coded rows; sortable and filterable
- Source column distinguishes NWS API vs WX Radio RF vs Cached
- Row click → map flies to that alert's polygon

### Panel 7 — System Status Panel
- SDR: Connected / Disconnected / Recording 137 MHz / Listening 162 MHz
- Operating Mode badge (DUAL / SDR_OFFLINE / API_ONLY / DEGRADED)
- Map tile source indicator (OSM / CartoDB / Local / SVG Fallback)
- Internet connectivity dot
- TLE age indicator with freshness bar
- Disk usage gauge; CPU/Memory

### Panel 8 — Pass Schedule Table
- Upcoming 24h passes; highlights next pass

---

### New JS Files Required (add to scaffold)
```
ui/static/js/
    alert_map.js          # Leaflet map init, polygon rendering, zoom logic
    tile_switcher.js      # Switches tile provider (OSM / CartoDB / local) at runtime
    ground_track.js       # Draws satellite ground track on the Leaflet map
    apt_overlay.js        # Drapes APT image onto map as L.imageOverlay
    county_lookup.js      # Offline: maps FIPS codes → county GeoJSON polygons
```

---

## 🧪 Testing Strategy

```python
# tests/test_mode_resolver.py
def test_resolve_mode_dual_when_hardware_and_internet(mocker):
    mocker.patch("core.mode_resolver.SDRController.is_hardware_present", return_value=True)
    mocker.patch("core.mode_resolver.is_internet_available", return_value=True)
    assert resolve_mode() == OperatingMode.DUAL

def test_resolve_mode_sdr_offline_when_no_internet(mocker):
    mocker.patch("core.mode_resolver.SDRController.is_hardware_present", return_value=True)
    mocker.patch("core.mode_resolver.is_internet_available", return_value=False)
    assert resolve_mode() == OperatingMode.SDR_OFFLINE

def test_resolve_mode_degraded_when_nothing(mocker):
    mocker.patch("core.mode_resolver.SDRController.is_hardware_present", return_value=False)
    mocker.patch("core.mode_resolver.is_internet_available", return_value=False)
    assert resolve_mode() == OperatingMode.DEGRADED

# tests/test_tle_staleness.py
def test_tle_is_usable_when_fresh(tmp_path, monkeypatch):
    # Write a TLE file with current mtime
    tle_file = tmp_path / "weather.tle"
    tle_file.write_text("TLE DATA")
    monkeypatch.setattr("orbital.tle_staleness.get_tle_age_hours", lambda: 2.0)
    usable, _ = tle_is_usable()
    assert usable is True

def test_tle_not_usable_when_too_old(monkeypatch):
    monkeypatch.setattr("orbital.tle_staleness.get_tle_age_hours", lambda: 80.0)
    usable, reason = tle_is_usable()
    assert usable is False
    assert "80h old" in reason

# tests/test_same_decoder.py
def test_parse_tornado_warning_same_string():
    # SAME string for a Tornado Warning in Cook County, IL
    same_string = "ZCZC-WXR-TOR-017031+0030-1921523-KLOT/NWS-"
    alerts = _parse_same_string(same_string)
    assert alerts[0].event_code == "TOR"
    assert alerts[0].event_name == "Tornado Warning"
    assert alerts[0].ui_level == "critical"

# tests/test_alert_merger.py
def test_merger_deduplicates_same_event_from_multiple_sources():
    nws = [make_alert(event="Tornado Warning", area="Cook County")]
    same = [make_same_alert(event_code="TOR", fips=["017031"])]
    result = merge_alerts(nws, same, [], internet_available=True)
    assert len(result) == 1  # Deduplicated
    assert result[0].source == "nws_api"  # NWS takes priority
```

---

## 🔮 Suggested Next Steps & Improvements

### 🥇 Phase 2 — Near-Term (1–3 months)

| Feature | Description | Complexity |
|---|---|---|
| **Meteor-M2 LRPT Decoder** | Add `meteor-demod` + `medet` pipeline for full-color Meteor imagery | High |
| **Two-SDR Support** | Second dongle stays on 162 MHz continuously while first handles 137 MHz | Medium |
| **Auto-antenna Rotator** | Drive a pan-tilt servo to track satellite az/el in real time | High |
| **Signal Quality Metrics** | Log SNR per pass, graph quality over time to optimize antenna placement | Medium |
| **NWS Hourly Forecast** | Pull and display hourly forecast text on dashboard when online | Low |
| **Discord / ntfy Alerts** | Forward critical alerts to Discord webhook or ntfy.sh push | Low |

### 🥈 Phase 3 — Medium-Term (3–6 months)

| Feature | Description | Complexity |
|---|---|---|
| **Whisper AI WX Radio Transcription** | Record 162 MHz audio and transcribe spoken forecast via Whisper | High |
| **Historical Pass Archive** | Full SQLite gallery with search, filter by satellite/date | Medium |
| **ML Image Enhancement** | PyTorch super-resolution model to sharpen noisy APT images | High |
| **Lightning Strike Overlay** | Blitzortung API to overlay real-time lightning on satellite imagery | Medium |
| **Mobile PWA** | Progressive Web App for home-screen install on iOS/Android | Medium |
| **AI Cloud Cover Analysis** | CNN to classify cloud types and estimate coverage % offline | High |

### 🥉 Phase 4 — Long-Term (6+ months)

| Feature | Description | Complexity |
|---|---|---|
| **GOES-16 LRIT Reception** | Full-disk geostationary imagery — dedicated hardware + DVB-S2 needed | Very High |
| **Home Assistant Integration** | Expose mode, alerts, pass data as HA sensors; trigger automations on warnings | Medium |
| **Multi-Station Mesh** | Multiple pi_noaa units sharing data (useful for storm spotter networks) | Very High |
| **Custom Alert Geofencing** | Alert only when storm polygon intersects user-defined area (GeoJSON) | High |
| **Solar & Space Weather** | Integrate NOAA SWPC API for solar flare / geomagnetic storm data | Medium |
| **3D Orbital Globe** | Cesium.js real-time satellite positions on a 3D globe | Medium |

---

## 📚 Key References & Resources

| Resource | URL |
|---|---|
| NWS Alerts API Docs | https://www.weather.gov/documentation/services-web-api |
| NWS Alert Zone Finder | https://alerts.weather.gov/ |
| NOAA WR SAME Specification | https://www.nws.noaa.gov/nwr/info/samemsg.html |
| NOAA WR County Coverage | https://www.nws.noaa.gov/nwr/coverage/county_coverage.html |
| Celestrak TLE Source | https://celestrak.org/NORAD/elements/ |
| NOAA APT Decoding Guide | https://noaa-apt.mbernardi.com.ar/ |
| aptdec GitHub | https://github.com/csete/aptdec |
| multimon-ng (SAME decoder) | https://github.com/EliasOenal/multimon-ng |
| pyorbital Docs | https://pyorbital.readthedocs.io/ |
| RTL-SDR Blog Tutorials | https://www.rtl-sdr.com/category/weather-satellites/ |
| NOAA Satellite Status | https://www.ospo.noaa.gov/Operations/POES/status.html |

---

> **Hardware Tip:** A second RTL-SDR dongle (~$25) eliminates the scheduling conflict
> between 137 MHz satellite reception and 162 MHz WX Radio monitoring. With two dongles,
> WX Radio SAME decoding runs 24/7 continuously in the background, while the first
> dongle is dedicated to satellite passes. This is the recommended production setup.

> **Offline First-Run Requirement:** The TLE cache must be populated at least once with
> an internet connection. After that, the system operates offline for up to 72 hours
> before pass prediction accuracy degrades meaningfully.
