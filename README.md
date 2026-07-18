# pi_noaa — Weather Satellite Receiving Station

pi_noaa is a full-stack Python application that receives, decodes, and visualizes real-time weather data from orbiting NOAA APT satellites and local NWS alerts using an RTL-SDR USB dongle.

It features a three-source alert pipeline:
1. **NWS API** (online)
2. **NOAA Weather Radio RF** (offline-capable)
3. **SQLite local cache** (degraded mode fallback)

## What it does
- Predicts overhead satellite passes (NOAA 15, 18, 19).
- Records passes via SDR and decodes APT images.
- Listens to 162 MHz NOAA Weather radio and decodes SAME alerts directly from the RF signal.
- Fetches active alerts from the National Weather Service.
- Serves an interactive dashboard mapping active alerts and displaying satellite images.

## Hardware you need
- **RTL-SDR v3 or v4 Dongle** (~$30)
- **V-Dipole or QFH Antenna** (V-Dipole is easiest to build, elements ~53.4cm long, spread 120 degrees horizontally).
- **Raspberry Pi 4** (or better) or any Linux PC.

## Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/yourname/pi_noaa.git
cd pi_noaa
```

### 2. Run the installer
```bash
chmod +x scripts/install_deps.sh
./scripts/install_deps.sh
```

### 3. Configure
Copy `config.yaml` to match your local setup.
- Set `location.latitude` and `location.longitude`
- Set `nws_api.alert_zone` (e.g. ILC031 for Cook County, IL)

### 4. First-run checks
Activate your virtual environment before running any python commands:
```bash
source venv/bin/activate
```

Ensure your SDR is detected:
```bash
python main.py --check-hardware
```

Scan for your strongest local WX Radio frequency:
```bash
python main.py --scan-wx-radio
```
Add the best frequency to your `config.yaml` under `noaa_weather_radio.preferred_frequency_hz`.

### 5. Start the station
```bash
# Must have internet on first run to fetch TLEs!
python main.py
```

### 6. Open the dashboard
Open `http://<your-pi-ip>:5000` in a web browser.

## Configuration Reference

### Operating Modes
- **auto**: Detects internet and hardware, picks best mode (recommended).
- **dual**: Forces SDR + API.
- **sdr_offline**: Forces SDR + SAME radio (no NWS API).
- **api_only**: Forces NWS API (no SDR used).

### Satellite Targets
- `frequency_hz`: SDR tuning frequency. **Requires NO INTERNET.** Fixed internationally.
- `norad_id`: Used to fetch orbital TLE data. **Requires Internet** (but caches for offline use up to 72 hours).

### NOAA Weather Radio (162 MHz, offline alerts)
The app time-shares the SDR. Between satellite passes, it tunes to your local NWS transmitter (162.x MHz) and decodes SAME FSK bursts to give you tornado/flood alerts even if the internet is down.

## Understanding the Dashboard

- **Alert Map**: Shows active weather alerts as colored polygons.
- **Alert Severity Colors**: Red (Critical), Orange (High), Yellow (Moderate), Blue (Info).
- **Connectivity Banners**: Tells you if you are in offline or degraded mode.
- **Satellite Image Panel**: Shows the most recent decoded APT satellite imagery.

## Troubleshooting

- **SDR not detected**:
  1. Check if the OS sees the USB device by running `lsusb`. Look for something like `Realtek Semiconductor Corp. RTL2838 DVB-T`.
  2. Check if the driver is accessible by running `rtl_test -t`. This tests if the OS has claimed it as a TV tuner. If this fails, run `scripts/setup_rtlsdr.sh`, then unplug and replug the SDR (or reboot the Pi) so the TV tuner driver is blacklisted properly.
- **UI shows "Recording..." but no files/images are generated**: 
  1. Ensure your SDR hardware is fully connected and detected (`rtl_test -t` completes or runs without immediate error). If the backend fails to detect the SDR, it falls back to `api_only` mode and skips recording entirely, even though the frontend UI timer will still tick down and show "Recording".
  2. Ensure your codebase is up to date. Previous versions had a bug where `pyorbital` would skip currently active passes, causing the backend to miss the recording window.
- **No satellite passes shown**: Ensure your system time is correct and you have an initial internet connection to download TLEs.
- **Map tiles not appearing offline**: You need to download an `.mbtiles` file and run `tileserver-gl`. (Detailed guide coming soon).

### SatDump Compilation & Space Management
During the dependency installation, SatDump is built from source and the source files are retained in `~/satdump`.

- **Why is this folder retained?**
  Leaving the repository in `~/satdump` allows you to compile updates in under **10 seconds** rather than rebuilding from scratch for 10+ minutes. To update SatDump in the future, simply run:
  ```bash
  cd ~/satdump/build && git pull && make -j2 && sudo make install
  ```
- **Where are the compilation logs?**
  All compilation output (standard output and errors) from the latest build is written to:
  `~/satdump/satdump_build.log`
  You can check this file if you run into installation issues.
- **How much space does it take?**
  The directory takes up roughly **600MB to 1GB** of storage.
- **Can I delete it?**
  Yes. If you are running low on SD card space, you can safely delete this folder and clean up your Pi. We have provided a post-installation cleanup script that automates this:
  ```bash
  chmod +x scripts/cleanup.sh
  ./scripts/cleanup.sh
  ```
  This script will safely delete `~/satdump` (saving ~1GB of space), clear your system's package cache (`apt-get clean`), and clean up temporary python compiler caches.
  
  Deleting these build-related folders **will not affect** the operation of `pi_noaa`, as the compiled binary is installed system-wide at `/usr/local/bin/satdump`. You will only need to run the installer again if you want to update SatDump to a newer version in the future.
