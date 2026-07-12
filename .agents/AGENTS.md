# pi_noaa — AGENTS.md
## Agentic AI Integration Guide

### Project Summary
pi_noaa is a Python application that receives weather satellite imagery (APT) and weather alerts via NWS API and 162MHz RF. It features a responsive mode resolver (`DUAL`, `SDR_OFFLINE`, `API_ONLY`, `DEGRADED`) to handle internet or hardware failures gracefully.

### Architecture Map
- `core/config_loader.py`: Config ALWAYS comes from `get_config()` — never parse YAML directly.
- `alerts/alert_classifier.py`: Alert classification and colors.
- `alerts/cache_store.py`: SQLite cache operations.
- `sdr/sdr_controller.py`: SDR hardware manager. Never call `rtl_fm` directly.

### Configuration Rules
- ALL tunable parameters must live in `config.yaml`, not in source code.
- If adding a new parameter, add it to BOTH `config.yaml` AND the Pydantic model in `core/config_loader.py`.
- Never hardcode frequencies, API URLs, file paths, or thresholds.

### Safety Rules for Agents
- Never call `sdr_controller.start_recording()` without first checking `is_hardware_present()`.
- Never DELETE files in `data/images/` or `data/recordings/` (user data).
- Never modify `data/pi_noaa.db` schema without creating a migration.
- Never commit credentials, API keys, or passwords.
- The `main.py --check-hardware` and `--check-connectivity` flags are safe to run at any time.

### Task Patterns (how to accomplish common tasks)

#### Adding a new alert event classification
1. Add the event name string to the correct list in `config.yaml` (`critical_events` / `high_events` / `moderate_events`).
2. No code changes needed.

#### Adding a new satellite to track
1. Add entry to `satellites` list in `config.yaml` with `name`, `norad_id`, `frequency_hz`, `signal_type`, `enabled`, `min_elevation_deg`.
2. No code changes needed.

#### Adding a new API route
1. Create new file in `api/routes/`.
2. Define FastAPI router.
3. Import and register in `api/server.py`.

#### Adding a new WebSocket event
1. Define the emit in `api/server.py`.
2. Document the event payload shape in this file.

#### Changing map styling
1. Edit `map` section of `config.yaml`.
2. `alert_map.js` reads all styling from `/api/config/map` — no JS changes needed.

### WebSocket Events Reference
| Event name       | Direction      | Payload description                      |
|---|---|---|
| `new_alert`      | server→client  | Single `UnifiedAlert` dict                 |
| `alerts_update`  | server→client  | Full list of active `UnifiedAlert` dicts   |
| `pass_update`    | server→client  | Current satellite position (az, el, etc.)|
| `mode_change`    | server→client  | New `OperatingMode` string                 |
| `system_status`  | server→client  | SDR state, disk, CPU, TLE age            |

### REST API Reference
| Endpoint                    | Method | Description                         |
|---|---|---|
| `/api/alerts`               | GET    | All active merged alerts             |
| `/api/passes`               | GET    | Upcoming satellite passes            |
| `/api/passes/next`          | GET    | Next single pass                     |
| `/api/images`               | GET    | Image metadata list                  |
| `/api/status`               | GET    | System health                        |
| `/api/config/map`           | GET    | Map config (safe, no secrets)        |
| `/api/config/observer`      | GET    | Observer lat/lon                     |

### Testing Requirements
- Every new Python module MUST have a corresponding test file in `tests/`.
- Tests MUST mock all external calls (httpx, subprocess, socket).
- Tests MUST NOT require SDR hardware to run.
- Use `pytest-asyncio` for async tests, `respx` for httpx mocking.
- Run tests with: `pytest tests/ -v`.

### Dependency Rules (no circular imports)
- `core` → (no internal deps)
- `sdr` → `core`
- `orbital` → `core`
- `wx_radio` → `core`
- `alerts` → `core`, `wx_radio` (same_codes only)
- `api` → `core`, `orbital`, `sdr`, `wx_radio`, `alerts`
- `ui` → (served by api, no Python imports)
