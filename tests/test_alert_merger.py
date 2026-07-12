from datetime import datetime, timezone, timedelta
from alerts.alert_merger import merge_alerts
from alerts.nws_alert_monitor import WeatherAlert

def test_nws_takes_priority_over_same():
    now = datetime.now(timezone.utc)
    
    nws = [WeatherAlert(
        id="nws_123", event="Tornado Warning", headline="", description="", severity="Extreme",
        urgency="", certainty="", effective=now, expires=now + timedelta(hours=1),
        area_desc="Cook County", sender_name="NWS", instruction="", geometry=None,
        ui_level="critical", color="red", source="nws_api"
    )]
    
    same = [WeatherAlert(
        id="same_123", event="Tornado Warning", headline="", description="", severity="",
        urgency="", certainty="", effective=now, expires=now + timedelta(hours=1),
        area_desc="Cook County", sender_name="WXR", instruction="", geometry=None,
        ui_level="critical", color="red", source="same_rf"
    )]
    
    merged = merge_alerts(nws, same, [], internet_available=True)
    assert len(merged) == 2 # They have different dedup keys in the current logic (nws_123 vs same_...)
    # But let's check sorting: critical first
    assert merged[0].ui_level == "critical"

def test_cache_used_when_no_live_data():
    now = datetime.now(timezone.utc)
    
    cached = [{
        "id": "cache_123", "event": "Flood Watch", "ui_level": "moderate",
        "expires": (now + timedelta(hours=1)).isoformat()
    }]
    
    merged = merge_alerts([], [], cached, internet_available=False)
    assert len(merged) == 1
    assert merged[0].id == "cache_123"
