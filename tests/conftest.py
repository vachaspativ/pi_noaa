import pytest
import shutil
from pathlib import Path

# Provide a mock config path
@pytest.fixture
def mock_config_path(tmp_path):
    config_str = """
location:
  latitude: 41.88
  longitude: -87.62
  altitude_m: 182
mode:
  primary: "auto"
  recheck_interval_minutes: 10
sdr:
  device_index: 0
  sample_rate_hz: 2400000
  ppm_correction: 0
  gain_mode: "auto"
  gain_db: 49.6
  bias_tee: false
satellites:
  - name: "NOAA 15"
    norad_id: 25338
    frequency_hz: 137620000
    signal_type: "APT"
    enabled: true
    min_elevation_deg: 10
tle:
  weather_tle_url: "http://example.com/tle"
  cache_dir: "{tmp}/tle_cache"
  tle_filename: "weather.tle"
  cache_ttl_hours: 6
  stale_tle_max_age_hours: 72
  warn_if_stale_after_hours: 24
  fallback_to_cached_passes: true
pass_prediction:
  lookahead_hours: 24
  max_passes_displayed: 10
  scheduler_interval_minutes: 60
recording:
  output_dir: "{tmp}/recordings"
  format: "wav"
  sample_rate_hz: 48000
  max_recording_minutes: 20
  keep_raw_recordings: false
satdump_decoder:
  backend: "satdump"
  output_dir: "{tmp}/images"
  satdump_path: "satdump"
  image_format: "png"
  keep_products: ["msa", "mcir", "therm", "1", "2"]
image:
  output_dir: "{tmp}/images"
  thumbnail_size: [320, 240]
  colormap: "thermal"
noaa_weather_radio:
  enabled: true
  frequencies_hz: [162400000]
  same_decoder:
    enabled: true
    fips_filter: []
    accept_all_areas: true
nws_api:
  base_url: "https://api.weather.gov"
  alert_zone: "ILC031"
  poll_interval_seconds: 60
  request_timeout_seconds: 15
  user_agent: "test/1.0"
alert_classification:
  critical_events: ["Tornado Warning"]
  high_events: ["Severe Thunderstorm Warning"]
  moderate_events: ["Flood Watch", "Flash Flood Watch"]
offline_cache:
  db_path: "{tmp}/pi_noaa.db"
  max_cached_alerts: 200
connectivity:
  probe_host: "example.com"
  probe_port: 80
map:
  tile_provider: "osm"
  initial_zoom: 6
geo:
  county_boundaries_path: "data/geo/us_counties_simplified.geojson"
  state_boundaries_path: "data/geo/us_states.geojson"
server:
  host: "127.0.0.1"
  port: 5000
websocket:
  pass_update_interval_seconds: 5
storage:
  data_root: "{tmp}"
logging:
  level: "INFO"
  log_dir: "{tmp}/logs"
notifications:
  enabled: false
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_str.replace("{tmp}", tmp_path.as_posix()))
    return str(config_file)

@pytest.fixture(autouse=True)
def setup_config(mock_config_path, monkeypatch):
    import core.config_loader
    monkeypatch.setattr(core.config_loader, "CONFIG_PATH", Path(mock_config_path))
    core.config_loader.get_config.cache_clear()
    
@pytest.fixture(autouse=True)
def reset_sdr_singleton():
    """Reset SDRController singleton between tests to prevent state leaks."""
    from sdr.sdr_controller import SDRController
    SDRController._instance = None
    SDRController._init_done = False
    yield
    SDRController._instance = None
    SDRController._init_done = False

@pytest.fixture
def clean_db(tmp_path):
    # Ensure fresh DB per test
    db_path = tmp_path / "pi_noaa.db"
    if db_path.exists():
        db_path.unlink()
    
    import alerts.cache_store
    alerts.cache_store._db_initialized = False
    return db_path
