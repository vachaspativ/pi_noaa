import pytest
import httpx
import respx
from alerts.nws_alert_monitor import NWSAlertMonitor

@pytest.mark.asyncio
async def test_fetch_alerts_classifies_tornado_as_critical(clean_db):
    monitor = NWSAlertMonitor()
    
    with respx.mock:
        respx.get("https://api.weather.gov/alerts/active/zone/ILC031").mock(
            return_value=httpx.Response(200, json={
                "features": [{
                    "properties": {
                        "id": "123",
                        "event": "Tornado Warning",
                        "severity": "Extreme",
                        "effective": "2023-10-10T12:00:00Z",
                        "expires": "2040-10-10T13:00:00Z"
                    }
                }]
            })
        )
        
        alerts = await monitor.fetch_alerts()
        assert len(alerts) == 1
        assert alerts[0].ui_level == "critical"

@pytest.mark.asyncio
async def test_new_alert_fires_callback(clean_db):
    monitor = NWSAlertMonitor()
    called = False
    
    def cb(alert):
        nonlocal called
        called = True
        
    monitor.on_new_alert(cb)
    
    with respx.mock:
        respx.get("https://api.weather.gov/alerts/active/zone/ILC031").mock(
            return_value=httpx.Response(200, json={
                "features": [{
                    "properties": {
                        "id": "123",
                        "event": "Tornado Warning",
                        "expires": "2040-10-10T13:00:00Z"
                    }
                }]
            })
        )
        
        await monitor.fetch_alerts()
        assert called == True

@pytest.mark.asyncio
async def test_duplicate_alert_no_callback(clean_db):
    monitor = NWSAlertMonitor()
    calls = 0
    
    def cb(alert):
        nonlocal calls
        calls += 1
        
    monitor.on_new_alert(cb)
    
    with respx.mock:
        respx.get("https://api.weather.gov/alerts/active/zone/ILC031").mock(
            return_value=httpx.Response(200, json={
                "features": [{
                    "properties": {
                        "id": "123",
                        "event": "Tornado Warning",
                        "expires": "2040-10-10T13:00:00Z"
                    }
                }]
            })
        )
        
        await monitor.fetch_alerts()
        await monitor.fetch_alerts()
        assert calls == 1
