from alerts.alert_classifier import classify_alert

def test_tornado_warning_is_critical():
    level, _ = classify_alert("Tornado Warning")
    assert level == "critical"

def test_flood_watch_is_moderate():
    level, _ = classify_alert("Flood Watch")
    assert level == "moderate"

def test_unknown_event_is_info():
    level, _ = classify_alert("Unknown Event", "Minor")
    assert level == "info"
