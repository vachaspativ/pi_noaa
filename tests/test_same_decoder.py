from wx_radio.same_decoder import parse_same_string, _classify_same_event, _passes_fips_filter

def test_parse_tornado_warning():
    # Example SAME string for Tornado Warning
    same = "ZCZC-WXR-TOR-017031+0030-1921523-KLOT/NWS-"
    alert = parse_same_string(same)
    assert alert is not None
    assert alert.event_code == "TOR"
    assert "017031" in alert.fips_codes
    assert alert.duration_minutes == 30
    assert alert.ui_level == "critical"

def test_classify_tornado_as_critical():
    assert _classify_same_event("TOR") == "critical"

def test_classify_flood_watch_as_moderate():
    assert _classify_same_event("FFA") == "moderate"

def test_fips_filter_accepts_matching_county():
    # accept_all_areas is true in mock config, so it should always pass
    assert _passes_fips_filter(["017031"]) == True
