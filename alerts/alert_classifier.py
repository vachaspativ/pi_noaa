"""
Classifies weather alerts into severity levels based on configuration.
Provides UI color mappings.
"""
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)

# UI Colors mapping for different severity levels
LEVEL_COLORS = {
    "critical": "#ef4444", # Red
    "high": "#f97316",     # Orange
    "moderate": "#eab308", # Yellow
    "info": "#3b82f6"      # Blue
}

BORDER_COLORS = {
    "critical": "#dc2626",
    "high": "#ea580c",
    "moderate": "#ca8a04",
    "info": "#2563eb"
}


def classify_alert(event: str, severity: str = "") -> tuple[str, str]:
    """
    Classify an alert into a UI level and return its assigned hex color.
    
    Args:
        event: The event name (e.g. "Tornado Warning").
        severity: The NWS severity string (optional, used as fallback).
        
    Returns:
        tuple (ui_level, hex_color)
    """
    cfg = get_config().alert_classification
    
    if event in cfg.get("critical_events", []):
        level = "critical"
    elif event in cfg.get("high_events", []):
        level = "high"
    elif event in cfg.get("moderate_events", []):
        level = "moderate"
    else:
        # Fallback to NWS severity string if event name wasn't mapped
        severity_lower = severity.lower()
        if severity_lower == "extreme":
            level = "critical"
        elif severity_lower == "severe":
            level = "high"
        elif severity_lower == "moderate":
            level = "moderate"
        else:
            level = "info"
            
    return level, LEVEL_COLORS[level]
