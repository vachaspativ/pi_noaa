from core.config_loader import get_config

def test_config_loader_parses_yaml():
    cfg = get_config()
    assert cfg.location["latitude"] == 41.88
    assert cfg.nws_api["alert_zone"] == "ILC031"
    assert len(cfg.satellites) == 1
    assert cfg.satellites[0].name == "NOAA 15"
