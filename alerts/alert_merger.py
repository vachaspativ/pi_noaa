"""
Merges alerts from NWS API, SAME RF, and SQLite cache into a unified list.
Handles deduplication and prioritization (API > RF > Cache).
"""
import dateutil.parser
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Any
from alerts.nws_alert_monitor import WeatherAlert
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class UnifiedAlert:
    id: str
    event: str
    headline: str
    description: str
    severity: str
    ui_level: str
    color: str
    effective: str # ISO format for JSON serialization
    expires: str   # ISO format
    area_desc: str
    source: str
    geometry: Optional[dict] = None
    is_stale: bool = False


# Sort order weights for UI
UI_LEVEL_WEIGHT = {
    "critical": 0,
    "high": 1,
    "moderate": 2,
    "info": 3
}


def merge_alerts(
    nws_alerts: list[WeatherAlert],
    same_alerts: list[WeatherAlert],
    cached_alerts: list[dict],
    internet_available: bool
) -> list[UnifiedAlert]:
    """
    Merge multiple sources into a single deduplicated, sorted list.
    
    Args:
        nws_alerts: Live alerts from NWS API
        same_alerts: Live alerts from SAME RF decoder
        cached_alerts: Stale alerts from SQLite cache
        internet_available: Boolean, if True we ignore cache entirely
        
    Returns:
        List of UnifiedAlerts, sorted by severity then recency.
    """
    merged_map: dict[str, UnifiedAlert] = {}
    
    # 1. Process Cached Alerts (lowest priority)
    # Only if we don't have internet. If we have internet, the cache is not needed for display.
    if not internet_available:
        for ca in cached_alerts:
            # Check expiration
            try:
                expires = dateutil.parser.parse(ca.get("expires", ""))
                if expires < datetime.now(timezone.utc):
                    continue
            except Exception:
                continue
                
            event = ca.get("event", "")
            # Dedup key: we don't have a reliable single area key across sources,
            # so we'll just use the alert ID from the cache which is usually the NWS ID
            dedup_key = ca.get("id", "")
            
            merged_map[dedup_key] = UnifiedAlert(
                id=ca.get("id", ""),
                event=event,
                headline=ca.get("headline", ""),
                description=ca.get("description", ""),
                severity=ca.get("severity", ""),
                ui_level=ca.get("ui_level", "info"),
                color=ca.get("color", "#3b82f6"),
                effective=ca.get("effective", ""),
                expires=ca.get("expires", ""),
                area_desc=ca.get("area_desc", ""),
                source="cached",
                geometry=ca.get("geometry"),
                is_stale=True
            )
            
    # 2. Process SAME RF Alerts (medium priority)
    # Overwrites cache if there's a match
    for sa in same_alerts:
        # SAME alerts don't have a stable ID across issues, so dedup by event + area
        # This is a bit fuzzy but works for local RF
        dedup_key = f"same_{sa.event}_{sa.area_desc}"
        
        merged_map[dedup_key] = UnifiedAlert(
            id=sa.id,
            event=sa.event,
            headline=sa.headline,
            description=sa.description,
            severity=sa.severity,
            ui_level=sa.ui_level,
            color=sa.color,
            effective=sa.effective.isoformat(),
            expires=sa.expires.isoformat(),
            area_desc=sa.area_desc,
            source="same_rf",
            geometry=None, # SAME doesn't have geometry
            is_stale=False
        )
        
    # 3. Process NWS API Alerts (highest priority)
    # We use NWS alert ID as the key. If internet is up, this is the primary source.
    for na in nws_alerts:
        dedup_key = na.id
        
        merged_map[dedup_key] = UnifiedAlert(
            id=na.id,
            event=na.event,
            headline=na.headline,
            description=na.description,
            severity=na.severity,
            ui_level=na.ui_level,
            color=na.color,
            effective=na.effective.isoformat(),
            expires=na.expires.isoformat(),
            area_desc=na.area_desc,
            source="nws_api",
            geometry=na.geometry,
            is_stale=False
        )
        
    # Convert map to list
    final_list = list(merged_map.values())
    
    # Sort: ui_level (critical first) -> expires (soonest first)
    final_list.sort(key=lambda x: (
        UI_LEVEL_WEIGHT.get(x.ui_level, 99),
        x.expires
    ))
    
    return final_list
