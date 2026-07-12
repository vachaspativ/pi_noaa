from alerts.cache_store import save_alert, load_cached_alerts

def test_save_and_load_alert(clean_db):
    alert_data = {
        "id": "123",
        "event": "Tornado Warning",
        "ui_level": "critical",
        "source": "nws_api"
    }
    
    save_alert(alert_data)
    
    loaded = load_cached_alerts()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "123"
    assert loaded[0]["event"] == "Tornado Warning"

def test_empty_db_returns_empty_list(clean_db):
    loaded = load_cached_alerts()
    assert len(loaded) == 0

def test_rolling_window_cleanup(clean_db, monkeypatch):
    import core.config_loader
    cfg = core.config_loader.get_config()
    # Mock config to have small max_alerts
    cfg.offline_cache["max_cached_alerts"] = 2
    
    for i in range(5):
        save_alert({
            "id": str(i),
            "event": "Test",
            "ui_level": "info",
            "source": "test"
        })
        
    loaded = load_cached_alerts()
    assert len(loaded) == 2
    # The last 2 saved should remain (IDs 3 and 4)
    ids = [a["id"] for a in loaded]
    assert "3" in ids
    assert "4" in ids
