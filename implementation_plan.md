# 🛰️ pi_noaa — Phase 1 Implementation Plan

> **Scope:** Everything needed for a fully working v1.0 release — satellite pass
> prediction, SDR recording, APT image decoding, NWS API alerts, 162 MHz WX Radio
> SAME decoding, offline SQLite cache, interactive Leaflet map dashboard, and all
> supporting documentation for both human operators and agentic AI tools.
>
> **Source of truth:** [pi_noaa_project_prompt.md](file:///C:/Users/vacha/.gemini/antigravity/brain/a215147e-da2e-494b-82a6-92172b8b0459/pi_noaa_project_prompt.md)

---

## 📐 Phase 1 Deliverable Summary

| Area | Deliverable |
|---|---|
| **Foundation** | Full project scaffold, `config.yaml`, `requirements.txt` |
| **Core** | Config loader, logger, mode resolver, connectivity probe, scheduler |
| **SDR** | RTL-SDR controller, WAV recorder, APT decoder, image processor |
| **Orbital** | TLE fetcher + cache, staleness checker, pass predictor, satellite tracker |
| **WX Radio** | 162 MHz receiver, SAME decoder, SAME code map, frequency scanner |
| **Alerts** | NWS API client, NWS monitor, SAME monitor, merger, classifier, SQLite cache |
| **API** | FastAPI + Socket.IO server, all REST routes, WebSocket push |
| **UI** | Dark-theme dashboard, Leaflet alert map, alert banner, pass countdown, image panel |
| **Geo Data** | Bundled county + state GeoJSON files for offline polygon rendering |
| **Docs** | `README.md` (operator guide), `AGENTS.md` (agentic AI integration guide) |
| **Scripts** | `install_deps.sh`, `setup_rtlsdr.sh`, `scan_wx_radio.py`, `test_sdr.py` |
| **Tests** | Unit test suite covering all critical modules |

---

## 🗂️ Complete File Manifest

All files to be created in `c:\Users\vacha\code\pi_noaa\`:

```
pi_noaa/
│
├── [NEW] config.yaml
├── [NEW] requirements.txt
├── [NEW] README.md                          ← Operator + setup guide
├── [NEW] .agents/
│   └── [NEW] AGENTS.md                      ← Agentic AI integration rules
│
├── [NEW] main.py
│
├── [NEW] core/
│   ├── [NEW] __init__.py
│   ├── [NEW] config_loader.py
│   ├── [NEW] logger.py
│   ├── [NEW] connectivity.py
│   ├── [NEW] mode_resolver.py
│   └── [NEW] scheduler.py
│
├── [NEW] sdr/
│   ├── [NEW] __init__.py
│   ├── [NEW] sdr_controller.py
│   ├── [NEW] signal_recorder.py
│   ├── [NEW] apt_decoder.py
│   └── [NEW] image_processor.py
│
├── [NEW] orbital/
│   ├── [NEW] __init__.py
│   ├── [NEW] tle_fetcher.py
│   ├── [NEW] tle_staleness.py
│   ├── [NEW] pass_predictor.py
│   └── [NEW] satellite_tracker.py
│
├── [NEW] wx_radio/
│   ├── [NEW] __init__.py
│   ├── [NEW] wx_radio_receiver.py
│   ├── [NEW] same_decoder.py
│   ├── [NEW] same_codes.py
│   └── [NEW] frequency_scanner.py
│
├── [NEW] alerts/
│   ├── [NEW] __init__.py
│   ├── [NEW] nws_client.py
│   ├── [NEW] nws_alert_monitor.py
│   ├── [NEW] same_alert_monitor.py
│   ├── [NEW] alert_merger.py
│   ├── [NEW] alert_classifier.py
│   └── [NEW] cache_store.py
│
├── [NEW] api/
│   ├── [NEW] __init__.py
│   ├── [NEW] server.py
│   └── [NEW] routes/
│       ├── [NEW] __init__.py
│       ├── [NEW] passes.py
│       ├── [NEW] images.py
│       ├── [NEW] alerts.py
│       ├── [NEW] status.py
│       └── [NEW] config_view.py
│
├── [NEW] ui/
│   ├── [NEW] templates/
│   │   └── [NEW] index.html
│   └── [NEW] static/
│       ├── [NEW] css/
│       │   └── [NEW] dashboard.css
│       └── [NEW] js/
│           ├── [NEW] dashboard.js
│           ├── [NEW] alert_map.js
│           ├── [NEW] tile_switcher.js
│           ├── [NEW] ground_track.js
│           ├── [NEW] apt_overlay.js
│           ├── [NEW] county_lookup.js
│           ├── [NEW] alert_banner.js
│           ├── [NEW] offline_banner.js
│           └── [NEW] pass_clock.js
│
├── [NEW] data/
│   ├── [NEW] geo/
│   │   ├── [NEW] us_counties_simplified.geojson
│   │   └── [NEW] us_states.geojson
│   ├── tle_cache/               (auto-created at runtime)
│   ├── recordings/              (auto-created at runtime)
│   ├── images/                  (auto-created at runtime)
│   └── alerts/                  (auto-created at runtime)
│
├── [NEW] scripts/
│   ├── [NEW] install_deps.sh
│   ├── [NEW] setup_rtlsdr.sh
│   ├── [NEW] scan_wx_radio.py
│   └── [NEW] test_sdr.py
│
└── [NEW] tests/
    ├── [NEW] conftest.py
    ├── [NEW] test_config_loader.py
    ├── [NEW] test_connectivity.py
    ├── [NEW] test_mode_resolver.py
    ├── [NEW] test_tle_staleness.py
    ├── [NEW] test_pass_predictor.py
    ├── [NEW] test_same_decoder.py
    ├── [NEW] test_alert_classifier.py
    ├── [NEW] test_alert_merger.py
    ├── [NEW] test_nws_alert_monitor.py
    └── [NEW] test_cache_store.py
```

---

## ✅ Task Checklist

Tasks are ordered by dependency layer — each group can only start after the previous group is complete.

---

### 🔵 Layer 0 — Project Bootstrap

- [ ] **Create project root** at `c:\Users\vacha\code\pi_noaa\`
- [ ] **Initialize git repo** (`git init`, `.gitignore` for `venv/`, `data/`, `logs/`, `*.pyc`, `*.mbtiles`)
- [ ] **Write `requirements.txt`** (all packages from prompt; pin major versions)
- [ ] **Create Python virtual environment** (`python -m venv venv`)
- [ ] **Create empty `__init__.py`** in every package directory
- [ ] **Create all `data/` subdirectories** with `.gitkeep` files

---

### 🔵 Layer 1 — Configuration Foundation

> Nothing else can be built until `config.yaml` + `config_loader.py` exist and are tested.

- [ ] **Write `config.yaml`**
  - All sections: `location`, `mode`, `sdr`, `satellites`, `tle`, `pass_prediction`, `recording`, `apt_decoder`, `image`, `noaa_weather_radio`, `nws_api`, `alert_classification`, `offline_cache`, `connectivity`, `map`, `geo`, `server`, `websocket`, `storage`, `logging`, `notifications`
  - Inline comments explaining every parameter, especially frequency vs NORAD intent
  - Default values safe to run without SDR hardware (mode: `auto`)

- [ ] **Write `core/config_loader.py`**
  - `get_config()` with `@lru_cache` — singleton pattern
  - `reload_config()` — clears cache for hot-reload
  - Pydantic `AppConfig` model with nested `SatelliteConfig`
  - Raises `ConfigValidationError` on bad values with a human-readable message

- [ ] **Write `tests/test_config_loader.py`**
  - Test: valid config loads without error
  - Test: missing required field raises `ValidationError`
  - Test: `reload_config()` picks up changes (monkeypatch file)
  - Test: satellite frequency and NORAD ID are both required

---

### 🔵 Layer 2 — Core Infrastructure

- [ ] **Write `core/logger.py`**
  - `setup_logging(log_cfg: dict)` — configures rotating file handler + console
  - `get_logger(name: str)` — returns named logger
  - JSON format mode when `logging.json_format: true`

- [ ] **Write `core/connectivity.py`**
  - `is_internet_available() -> bool` — TCP probe to configured host
  - Primary + fallback host from config
  - Configurable timeout
  - `tests/test_connectivity.py` — mock socket.connect

- [ ] **Write `core/mode_resolver.py`**
  - `OperatingMode` enum: `DUAL`, `SDR_OFFLINE`, `API_ONLY`, `DEGRADED`
  - `resolve_mode() -> OperatingMode` — decision tree logic
  - `on_mode_change(callback)` — event registration
  - `tests/test_mode_resolver.py` — all four mode paths mocked

- [ ] **Write `core/scheduler.py`**
  - Wraps APScheduler `AsyncIOScheduler`
  - `add_interval_job(fn, minutes)` helper
  - `add_cron_job(fn, cron_str)` helper
  - `start()` / `shutdown()` lifecycle

---

### 🔵 Layer 3 — Orbital Engine

- [ ] **Write `orbital/tle_fetcher.py`**
  - `fetch_and_cache_tles()` — downloads from Celestrak URL in config, saves to `tle_cache/`
  - `get_tle_for_satellite(norad_id: int) -> tuple[str, str] | None`
  - Writes timestamp file alongside TLE cache for staleness tracking
  - Gracefully returns `None` (not raises) if cache is missing

- [ ] **Write `orbital/tle_staleness.py`**
  - `get_tle_age_hours() -> float | None`
  - `tle_is_usable() -> tuple[bool, str]` — checks against `stale_tle_max_age_hours`
  - `tle_staleness_banner() -> dict | None` — returns UI banner payload
  - `tests/test_tle_staleness.py` — mock file mtime at various ages

- [ ] **Write `orbital/pass_predictor.py`**
  - `SatellitePass` dataclass (AOS, LOS, max_el, az, duration, satellite info)
  - `get_upcoming_passes() -> list[SatellitePass]`
  - Filters by `min_elevation_deg` per satellite
  - Sorted by AOS ascending; capped at `max_passes_displayed`
  - Gracefully skips satellite if TLE unavailable (logs warning)
  - `tests/test_pass_predictor.py` — sorted order, elevation filter

- [ ] **Write `orbital/satellite_tracker.py`**
  - `get_current_position(sat_name, tle_lines) -> dict` — az, el, range, velocity
  - Called during active pass every N seconds for WebSocket push
  - Computes ground track (list of lat/lon points) for map overlay

---

### 🔵 Layer 4 — SDR Engine

- [ ] **Write `sdr/sdr_controller.py`**
  - `SDRController` class
  - `is_hardware_present() -> bool` — `rtl_test -t` subprocess check, 5s timeout
  - `start_recording(freq_hz, output_path) -> bool` — launches `rtl_fm | sox` pipeline
  - `stop_recording()` — terminates processes gracefully
  - `is_recording` property
  - Mutex guard: cannot start two recordings simultaneously

- [ ] **Write `sdr/signal_recorder.py`**
  - `record_pass(satellite_pass: SatellitePass) -> Path | None`
  - Orchestrates: arm at AOS − config minutes, record until LOS, stop, return WAV path
  - Enforces `max_recording_minutes` safety cap
  - Returns `None` if SDR unavailable

- [ ] **Write `sdr/apt_decoder.py`**
  - `decode_apt(wav_path: Path) -> Path | None` — wraps `aptdec` subprocess
  - Applies enhancements, map overlay, timestamp watermark from config
  - Returns output PNG path; `None` on decode failure
  - Logs stderr from aptdec for debugging

- [ ] **Write `sdr/image_processor.py`**
  - `apply_colormap(image_path: Path, colormap: str) -> Path`
  - `generate_thumbnail(image_path: Path) -> Path`
  - `rotate_for_pass_direction(image_path, is_northbound) -> Path`
  - `add_metadata_watermark(image_path, metadata: dict) -> Path`
  - Uses Pillow; reads `image` config section

---

### 🔵 Layer 5 — WX Radio & SAME Decoding

- [ ] **Write `wx_radio/same_codes.py`**
  - `SAME_EVENT_CODES: dict[str, str]` — all ~40 official SAME codes mapped to human names
  - Pure data file, no imports, no internet needed

- [ ] **Write `wx_radio/same_decoder.py`**
  - `SAMEAlert` dataclass (originator, event_code, event_name, fips_codes, duration, issued_at, call_sign, ui_level, source="same_rf")
  - `decode_same_from_wav(wav_path: str) -> list[SAMEAlert]`
  - Calls `multimon-ng -t wav -a EAS <wav>` subprocess
  - Parses SAME regex pattern from stdout
  - Applies FIPS filter from config
  - `_classify_same_event(event_code) -> str`
  - `tests/test_same_decoder.py` — test against known SAME strings

- [ ] **Write `wx_radio/frequency_scanner.py`**
  - `scan_frequencies() -> dict[int, float]` — returns freq → signal strength map
  - `get_best_frequency() -> int` — returns strongest freq
  - `scan_and_report()` — CLI utility used by `main.py --scan-wx-radio`

- [ ] **Write `wx_radio/wx_radio_receiver.py`**
  - `WXRadioReceiver` class
  - `start_monitoring(frequency_hz: int)`  — `rtl_fm` tuned to 162 MHz, pipes to `multimon-ng`
  - `stop_monitoring()`
  - Fires `on_same_alert(callback)` when a SAME message is decoded
  - Time-shares SDR: starts only when `sdr_controller.is_recording` is False

---

### 🔵 Layer 6 — Alert Pipeline

- [ ] **Write `alerts/alert_classifier.py`**
  - `classify_alert(event: str, severity: str) -> tuple[str, str]` — returns `(ui_level, hex_color)`
  - Reads `alert_classification` from config
  - `LEVEL_COLORS: dict` — critical/high/moderate/info → hex colors
  - Shared by both NWS and SAME sources

- [ ] **Write `alerts/cache_store.py`**
  - SQLite schema: `alerts`, `passes`, `images` tables
  - `save_alert(alert_data: dict)`
  - `load_cached_alerts() -> list[dict]`
  - `save_pass(pass_data: dict)` / `load_cached_passes()`
  - `save_image_metadata(meta: dict)`
  - Rolling window cleanup (max_cached_alerts from config)

- [ ] **Write `alerts/nws_client.py`**
  - `NWSClient` class with `httpx.AsyncClient`
  - `fetch_active_alerts(zone: str) -> list[dict]` — calls `api.weather.gov`
  - Returns raw feature list (GeoJSON features with geometry)
  - Raises `NWSAPIError` on non-200; caller handles gracefully
  - Adds required `User-Agent` header from config

- [ ] **Write `alerts/nws_alert_monitor.py`**
  - `NWSAlertMonitor` with `run_polling_loop()` async task
  - Converts raw NWS features → `WeatherAlert` dataclass
  - Deduplication by alert ID (`_seen_ids` set)
  - Fires `on_new_alert(callback)` for new alerts
  - Saves all alerts to `cache_store` (so cache is always fresh when online)
  - `tests/test_nws_alert_monitor.py` — mock httpx with `respx`

- [ ] **Write `alerts/same_alert_monitor.py`**
  - Wraps `WXRadioReceiver.on_same_alert` into the same `WeatherAlert` interface
  - Converts `SAMEAlert` → `WeatherAlert` (unified schema)
  - Fires registered callbacks using same interface as NWS monitor

- [ ] **Write `alerts/alert_merger.py`**
  - `merge_alerts(nws, same, cached, internet_available) -> list[UnifiedAlert]`
  - Priority: `nws_api > same_rf > cache`
  - Deduplication key: `f"{event}:{area_or_fips}"`
  - Sorts: level_order (critical first), then by recency
  - `tests/test_alert_merger.py` — dedup, priority, sort order

---

### 🔵 Layer 7 — API Server

- [ ] **Write `api/routes/passes.py`**
  - `GET /api/passes` — returns upcoming passes (JSON array)
  - `GET /api/passes/next` — returns only the next pass
  - `GET /api/passes/{norad_id}/position` — live az/el during pass

- [ ] **Write `api/routes/images.py`**
  - `GET /api/images` — list of decoded images (metadata + thumbnail URL)
  - `GET /api/images/{filename}` — serve full-size image
  - `GET /api/images/{filename}/thumbnail`

- [ ] **Write `api/routes/alerts.py`**
  - `GET /api/alerts` — all active merged alerts
  - `GET /api/alerts/{id}` — single alert full detail

- [ ] **Write `api/routes/status.py`**
  - `GET /api/status` — system health: mode, SDR state, TLE age, connectivity, disk, CPU/RAM

- [ ] **Write `api/routes/config_view.py`**
  - `GET /api/config/map` — returns map config section (used by `alert_map.js`)
  - `GET /api/config/observer` — returns lat/lon for map centering
  - Strips sensitive keys (auth passwords, etc.)

- [ ] **Write `api/server.py`**
  - FastAPI app + Socket.IO `AsyncServer`
  - `lifespan()` context manager: starts alert monitors, TLE scheduler, WX Radio receiver
  - Registers `on_new_alert` → `sio.emit("new_alert", ...)` WebSocket push
  - Registers `on_mode_change` → `sio.emit("mode_change", ...)` push
  - `build_app(mode: OperatingMode) -> ASGIApp`
  - WebSocket events: `new_alert`, `alerts_update`, `pass_update`, `mode_change`, `system_status`

- [ ] **Write `main.py`**
  - Argument parsing (`--check-hardware`, `--check-connectivity`, `--scan-wx-radio`)
  - Calls `resolve_mode()`, prints mode
  - TLE staleness check and human-readable warning
  - Launches `uvicorn` with `socket_app`

---

### 🔵 Layer 8 — UI Dashboard

- [ ] **Write `ui/static/css/dashboard.css`**
  - Dark theme: background `#0a0a0f`, surface `#12121a`, accent `#00e5ff`
  - CSS custom properties for all colors, opacities, spacing
  - Alert level color variables: `--color-critical`, `--color-high`, `--color-moderate`, `--color-info`
  - `@keyframes pulse-opacity` for critical polygon animation
  - `.pulse-polygon` class (applied via JS to Leaflet SVG paths)
  - CSS grid layout: alert banner (full width) → map (large) → sidebar panels
  - Responsive breakpoints: 1440px, 1024px, 768px

- [ ] **Write `ui/static/js/alert_map.js`**
  - Leaflet map init from `/api/config/map`
  - Base tile layer with runtime switching
  - Alert polygon layer group: `renderAlertPolygons(alerts)`
  - Fill opacity, stroke, color all from fetched config (never hardcoded)
  - Popup builder: `buildAlertPopup(alert) -> HTML string`
  - Pulsing CSS class for critical polygons
  - Auto-fit bounds on load; `flyToBounds` on alert click
  - Observer marker with custom SVG icon
  - WebSocket handlers: `alerts_update`, `new_alert`

- [ ] **Write `ui/static/js/county_lookup.js`**
  - Loads `us_counties_simplified.geojson` once (cached in memory)
  - `getCountyPolygons(fipsCodes: string[]) -> GeoJSON FeatureCollection`
  - Used by `alert_map.js` for SAME RF alerts that have no NWS geometry

- [ ] **Write `ui/static/js/ground_track.js`**
  - `drawGroundTrack(map, trackPoints)` — cyan dashed polyline
  - `clearGroundTrack(map)`
  - Called on `pass_update` WebSocket event

- [ ] **Write `ui/static/js/alert_banner.js`**
  - Horizontal scrolling ticker (CSS marquee) for active alerts
  - Color-coded item backgrounds by `ui_level`
  - Source badge (`[NWS API]` / `[WX Radio RF]` / `[Cached]`)
  - Click handler → calls `alert_map.js` `flyToAlert(alertId)`
  - Web Audio API chime on critical alert (configurable frequency, duration)

- [ ] **Write `ui/static/js/offline_banner.js`**
  - Top-of-page banner driven by `mode_change` WebSocket event
  - `DUAL` mode: no banner
  - `SDR_OFFLINE`: blue banner "📡 Offline Mode — Satellite + WX Radio Active"
  - `API_ONLY`: yellow banner "⚠ No SDR Hardware — Alert monitoring only"
  - `DEGRADED`: red pulsing banner "🔴 Fully Offline — Showing cached data"
  - TLE staleness: separate amber banner below

- [ ] **Write `ui/static/js/pass_clock.js`**
  - Countdown timer to next AOS (ticks every second client-side)
  - Updates from `/api/passes/next` on page load + every 5 min
  - Shows: satellite name, frequency, max elevation, duration
  - Progress bar during active pass (green fill, % of pass elapsed)

- [ ] **Write `ui/static/js/dashboard.js`**
  - Main entry point: initializes Socket.IO connection
  - Orchestrates all modules on page load
  - Handles `system_status` WebSocket events (SDR state, disk, CPU)

- [ ] **Write `ui/templates/index.html`**
  - Semantic HTML5 structure
  - CDN links: Leaflet.js CSS+JS, Socket.IO client
  - SEO meta tags: title, description, viewport
  - Layout regions: `#alert-banner`, `#map-panel`, `#sidebar`
  - Sidebar contains: pass countdown, latest image, alerts table, status panel, pass schedule
  - All panel `id` attributes unique and descriptive (for testability)
  - Inject observer lat/lon from Jinja2 template variables

---

### 🔵 Layer 9 — Geo Data

- [ ] **Download and bundle `data/geo/us_counties_simplified.geojson`**
  - Source: US Census Bureau TIGER/Line Shapefiles → converted to GeoJSON
  - Simplify with `mapshaper` or `shapely` to tolerance 0.01 (target: ~1.5 MB)
  - Properties retained per feature: `GEOID` (5-digit FIPS), `NAME`, `STATE`
  - Add a `scripts/download_geo_data.py` helper script

- [ ] **Download and bundle `data/geo/us_states.geojson`**
  - Same source; simplified state boundaries
  - Used for map context layer (drawn as thin grey outlines)
  - Target: ~150 KB

---

### 🔵 Layer 10 — Scripts

- [ ] **Write `scripts/install_deps.sh`**
  - `apt-get install`: `rtl-sdr`, `sox`, `librtlsdr-dev`, `build-essential`, `cmake`, `git`, `python3-pip`, `python3-venv`, `ffmpeg`, `multimon-ng`
  - Blacklist `dvb_usb_rtl28xxu` kernel module
  - Build and install `aptdec` from source
  - Create Python venv + `pip install -r requirements.txt`
  - Download geo data (calls `scripts/download_geo_data.py`)
  - Prints next steps

- [ ] **Write `scripts/setup_rtlsdr.sh`**
  - Writes udev rules for RTL-SDR (so it runs without sudo)
  - Adds current user to `plugdev` group
  - Reloads udev rules

- [ ] **Write `scripts/scan_wx_radio.py`**
  - Scans all 7 NOAA WX Radio frequencies
  - Reports signal strength for each
  - Prints recommended `preferred_frequency_hz` to add to config

- [ ] **Write `scripts/test_sdr.py`**
  - Checks `rtl_test` binary exists
  - Checks RTL-SDR hardware detected
  - Checks `aptdec` binary exists
  - Checks `multimon-ng` binary exists
  - Prints ✓/✗ for each check

- [ ] **Write `scripts/download_geo_data.py`**
  - Downloads county + state GeoJSON from Census Bureau
  - Runs simplification
  - Saves to `data/geo/`

---

### 🔵 Layer 11 — Documentation

#### `README.md`

The README must cover all of the following sections, in order:

```
# pi_noaa — Weather Satellite Receiving Station

## What it does
## Hardware you need
## Quick Start
  ### 1. Clone the repo
  ### 2. Run the installer
  ### 3. Configure
  ### 4. First-run checks
  ### 5. Start the station
  ### 6. Open the dashboard
## Configuration Reference
  ### Location
  ### Operating Modes
  ### Satellite Targets (frequencies vs NORAD IDs explained)
  ### NOAA Weather Radio (162 MHz, offline alerts)
  ### Alert Classification
  ### Map Settings
  ### Offline / Degraded Mode Behaviour
## Understanding the Dashboard
  ### Alert Map
  ### Alert Severity Colors
  ### Connectivity Banners
  ### Pass Countdown
  ### Satellite Image Panel
## Hardware Setup Tips
  ### RTL-SDR + Antenna
  ### V-Dipole antenna build guide (dimensions)
  ### Raspberry Pi recommendations
## System Requirements
## Troubleshooting
  ### SDR not detected
  ### No satellite passes shown
  ### Alerts not loading
  ### Map tiles not appearing offline
## Development
  ### Running tests
  ### Project structure overview
## License
```

**Key things README must explain clearly:**
- Why satellite frequencies are in config (hardware tuning) vs NORAD IDs (TLE lookup)
- The four operating modes and what each one does
- How offline alert capability works (162 MHz WX Radio → SAME decoder → county polygons from bundled GeoJSON)
- What `.mbtiles` is, how to download it for offline map tiles, and where to put it
- First-run internet requirement (to populate TLE cache)
- All `--check-hardware`, `--check-connectivity`, `--scan-wx-radio` CLI flags documented

---

#### `.agents/AGENTS.md`

This file tells agentic AI tools (Claude, Gemini, GPT-4, Antigravity, etc.) how to work safely and effectively in this codebase. It must include:

```markdown
# pi_noaa — AGENTS.md
## Agentic AI Integration Guide

### Project Summary
Brief description of what pi_noaa does, its operating modes, and key constraints.

### Architecture Map
Short summary of which module does what, so agents don't duplicate logic:
- config always comes from get_config() — never parse YAML directly
- Alert classification always goes through alert_classifier.py
- SQLite always accessed through cache_store.py
- SDR always managed through sdr_controller.py (never call rtl_fm directly)

### Configuration Rules
- ALL tunable parameters must live in config.yaml, not in source code
- If adding a new parameter, add it to BOTH config.yaml AND the Pydantic model
- Never hardcode frequencies, API URLs, file paths, or thresholds

### Safety Rules for Agents
- Never call sdr_controller.start_recording() without first checking is_hardware_present()
- Never DELETE files in data/images/ or data/recordings/ (user data)
- Never modify data/pi_noaa.db schema without creating a migration
- Never commit credentials, API keys, or passwords (use config.yaml + .gitignore)
- The main.py --check-hardware and --check-connectivity flags are safe to run at any time

### Task Patterns (how to accomplish common tasks)

#### Adding a new alert event classification
1. Add the event name string to the correct list in config.yaml
   (critical_events / high_events / moderate_events)
2. No code changes needed — alert_classifier.py reads from config

#### Adding a new satellite to track
1. Add entry to satellites list in config.yaml with:
   - name, norad_id, frequency_hz, signal_type, enabled, min_elevation_deg
2. No code changes needed

#### Adding a new API route
1. Create new file in api/routes/
2. Define FastAPI router
3. Import and register in api/server.py

#### Adding a new WebSocket event
1. Define the emit in api/server.py
2. Document the event payload shape in this file under "WebSocket Events"

#### Changing map styling
1. Edit map section of config.yaml
2. The /api/config/map endpoint will serve the updated values
3. alert_map.js reads all styling from this endpoint — no JS changes needed

### WebSocket Events Reference
| Event name       | Direction      | Payload description                      |
|---|---|---|
| new_alert        | server→client  | Single UnifiedAlert dict                 |
| alerts_update    | server→client  | Full list of active UnifiedAlert dicts   |
| pass_update      | server→client  | Current satellite position (az, el, etc.)|
| mode_change      | server→client  | New OperatingMode string                 |
| system_status    | server→client  | SDR state, disk, CPU, TLE age            |

### REST API Reference
| Endpoint                    | Method | Description                         |
|---|---|---|
| /api/alerts                 | GET    | All active merged alerts             |
| /api/passes                 | GET    | Upcoming satellite passes            |
| /api/passes/next            | GET    | Next single pass                     |
| /api/images                 | GET    | Image metadata list                  |
| /api/status                 | GET    | System health                        |
| /api/config/map             | GET    | Map config (safe, no secrets)        |
| /api/config/observer        | GET    | Observer lat/lon                     |

### Testing Requirements
- Every new Python module MUST have a corresponding test file in tests/
- Tests MUST mock all external calls (httpx, subprocess, socket)
- Tests MUST NOT require SDR hardware to run
- Use pytest-asyncio for async tests
- Use respx for httpx mocking
- Run tests with: pytest tests/ -v

### File Ownership Map
| File / Module           | Owns / Responsible For                     |
|---|---|
| core/config_loader.py   | All config access — single source of truth |
| core/mode_resolver.py   | Operating mode state                       |
| alerts/alert_merger.py  | Final unified alert list                   |
| alerts/cache_store.py   | All SQLite reads and writes                |
| api/server.py           | WebSocket emissions, lifespan management   |
| ui/static/js/alert_map.js | All Leaflet map operations              |

### Dependency Rules (no circular imports)
core → (no internal deps)
sdr → core
orbital → core
wx_radio → core
alerts → core, wx_radio (same_codes only)
api → core, orbital, sdr, wx_radio, alerts
ui → (served by api, no Python imports)
```

---

### 🔵 Layer 12 — Tests Completion

- [ ] **Write `tests/conftest.py`**
  - Shared fixtures: `mock_config`, `tmp_db_path`, `mock_nws_response`, `mock_same_wav`
  - `mock_config` fixture returns a fully valid AppConfig with test values

- [ ] **Write remaining test files** (all noted above in Layer 1–6 tasks)

- [ ] **Verify all tests pass** with `pytest tests/ -v --tb=short`
  - Tests must pass with no SDR hardware connected
  - Tests must pass with no internet connection (all external calls mocked)

---

## 🔗 Inter-Module Dependency Diagram

```
                ┌────────────────┐
                │  config.yaml   │
                └───────┬────────┘
                        │ get_config()
                ┌───────▼────────┐
                │ config_loader  │
                └───────┬────────┘
           ┌────────────┼────────────────────────┐
           │            │                        │
    ┌──────▼──────┐ ┌───▼──────────┐   ┌────────▼────────┐
    │ connectivity│ │    logger    │   │  mode_resolver  │
    └──────┬──────┘ └───┬──────────┘   └────────┬────────┘
           │            │                        │
    ┌──────▼────────────▼────────────────────────▼──────┐
    │                  scheduler                        │
    └──────┬────────────────────────────────────────────┘
           │
    ┌──────┼──────────────────────────────────┐
    │      │                                  │
┌───▼──┐ ┌─▼────────┐ ┌──────────┐  ┌────────▼───────┐
│ sdr/ │ │ orbital/ │ │ wx_radio/│  │    alerts/     │
│      │ │          │ │          │  │                │
│ sdr_ │ │ tle_     │ │ same_    │  │ nws_client     │
│ ctrl │ │ fetcher  │ │ decoder  │  │ nws_monitor    │
│ apt_ │ │ pass_    │ │ wx_rcvr  │  │ same_monitor   │
│ dec  │ │ predict  │ │          │  │ alert_merger   │
└───┬──┘ └─┬────────┘ └────┬─────┘  │ cache_store   │
    │      │               │        └────────┬───────┘
    └──────┴───────┬────────┘                │
                   │                         │
            ┌──────▼─────────────────────────▼──────┐
            │              api/server.py             │
            │         FastAPI + Socket.IO            │
            └──────────────────┬─────────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │   ui/ (browser)      │
                    │  Leaflet + Socket.IO │
                    └──────────────────────┘
```

---

## 🔍 Verification Plan

### Automated

```bash
# All tests, no hardware required
pytest tests/ -v --tb=short

# With coverage report
pytest tests/ --cov=. --cov-report=term-missing

# Type check
mypy core/ sdr/ orbital/ wx_radio/ alerts/ api/ --ignore-missing-imports
```

### Manual — Hardware Present

```bash
# 1. Hardware check
python main.py --check-hardware
# Expected: ✓ RTL-SDR found

# 2. Connectivity check
python main.py --check-connectivity
# Expected: ✓ Internet reachable

# 3. WX Radio frequency scan
python main.py --scan-wx-radio
# Expected: table of 7 frequencies + recommendation

# 4. Full startup
python main.py
# Expected: mode printed, dashboard at http://localhost:5000
```

### Manual — No Hardware (API Only Mode)

```bash
# 1. Force api_only mode
# In config.yaml: mode.primary = "api_only"
python main.py
# Expected: starts in API_ONLY mode, dashboard shows NWS alerts, no satellite imagery
```

### Manual — Fully Offline

```bash
# 1. Disconnect internet, force degraded
# In config.yaml: mode.primary = "degraded"
python main.py
# Expected: dashboard shows cached alerts with stale banner, map uses local tiles or SVG fallback
```

### UI Verification Checklist

- [ ] Alert map loads and shows base tiles
- [ ] Active NWS alerts render as color-coded polygons
- [ ] Clicking a polygon opens popup with alert details
- [ ] "Fit All Alerts" button zooms to all polygons
- [ ] Scrolling zoom and pinch-zoom work
- [ ] Alert ticker banner shows active alerts in correct severity colors
- [ ] Clicking ticker item flies map to that polygon
- [ ] Connectivity banner shows correct mode badge
- [ ] Pass countdown ticks live
- [ ] System status panel reflects real SDR/mode state
- [ ] Dark/Light tile switch works

---

## 📆 Suggested Build Order (by session)

| Session | Focus | Output |
|---|---|---|
| 1 | Layers 0–2 | Scaffold + config + core + tests passing |
| 2 | Layer 3 | Orbital engine + TLE cache + pass predictor |
| 3 | Layer 4 | SDR engine + WAV recorder + APT decoder |
| 4 | Layer 5 | WX Radio + SAME decoder + frequency scanner |
| 5 | Layer 6 | Full alert pipeline (NWS + SAME + merger + cache) |
| 6 | Layer 7 | API server + all routes + WebSocket |
| 7 | Layer 8 | UI dashboard + Leaflet map + all JS modules |
| 8 | Layers 9–10 | Geo data + install scripts |
| 9 | Layers 11–12 | README.md + AGENTS.md + final test run |

---

> [!IMPORTANT]
> The `.agents/AGENTS.md` file must be created **before any agentic AI tool is used to
> work on this codebase**. It is the contract between the codebase and any AI agent
> performing autonomous tasks. Without it, agents may make inconsistent decisions about
> config ownership, module boundaries, and safety rules.

> [!NOTE]
> `data/geo/us_counties_simplified.geojson` must be committed to the repo. It is the
> only "offline polygon source" for SAME RF alerts and is required for offline map
> functionality. At ~1.5 MB simplified, it is acceptable to commit to git.
> Do NOT commit `.mbtiles` files — they are too large and should be downloaded separately.
