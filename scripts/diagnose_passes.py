#!/usr/bin/env python3
"""
Diagnostic script to trace the full satellite pass prediction pipeline.
Checks each stage: config → TLE cache → TLE parsing → pyorbital prediction → API output.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config_loader import get_config


def main():
    print("=== Satellite Pass Prediction Diagnostic ===\n")
    
    # 1. Config check
    print("[1/5] Checking config.yaml...")
    cfg = get_config()
    loc = cfg.location
    lat = loc["latitude"]
    lon = loc["longitude"]
    alt_m = loc["altitude_m"]
    print(f"  Observer: lat={lat}, lon={lon}, alt={alt_m}m")
    
    enabled_sats = [s for s in cfg.satellites if s.enabled]
    print(f"  Enabled satellites: {len(enabled_sats)}")
    for s in enabled_sats:
        print(f"    - {s.name} (NORAD {s.norad_id}, min_el={s.min_elevation_deg}°)")

    pred_cfg = cfg.pass_prediction
    print(f"  Lookahead: {pred_cfg['lookahead_hours']} hours")
    print()

    # 2. TLE cache file check
    print("[2/5] Checking TLE cache file...")
    tle_cfg = cfg.tle
    cache_path = Path(tle_cfg["cache_dir"]) / tle_cfg["tle_filename"]
    
    # Always attempt a fresh fetch so we use the latest fetcher logic
    print("  ↻ Fetching fresh TLE data (group + individual satellites)...")
    from orbital.tle_fetcher import fetch_and_cache_tles
    result = fetch_and_cache_tles()
    if result:
        print(f"  ✓ TLE fetch successful.")
    else:
        print(f"  ✗ TLE fetch failed.")
    
    if not cache_path.exists():
        print(f"  ✗ TLE cache NOT FOUND at: {cache_path}")
        print("  → This is why passes are not being calculated!")
        sys.exit(1)
    
    size = cache_path.stat().st_size
    print(f"  ✓ TLE cache found: {cache_path} ({size} bytes)")
    print()

    # 3. TLE parsing for each satellite
    print("[3/5] Looking up TLE data for each enabled satellite...")
    from orbital.tle_fetcher import get_tle_for_satellite
    
    tle_results = {}
    for s in enabled_sats:
        tle = get_tle_for_satellite(s.norad_id)
        if tle is None:
            print(f"  ✗ {s.name} (NORAD {s.norad_id}): NOT FOUND in TLE cache")
        else:
            print(f"  ✓ {s.name} (NORAD {s.norad_id}): Found")
            print(f"    Line1: {tle[0][:40]}...")
            tle_results[s.norad_id] = tle
    
    if not tle_results:
        print("\n  ✗ No TLE data found for any enabled satellite!")
        print("  → The TLE file may not contain weather satellite entries.")
        print(f"  → Check the TLE URL: {tle_cfg['weather_tle_url']}")
        sys.exit(1)
    print()

    # 4. Pyorbital prediction
    print("[4/5] Running pyorbital pass prediction...")
    from datetime import datetime, timezone
    from pyorbital.orbital import Orbital

    alt_km = alt_m / 1000.0
    lookahead = pred_cfg["lookahead_hours"]
    utc_now = datetime.now(timezone.utc)
    print(f"  Current UTC: {utc_now.isoformat()}")

    total_passes = 0
    for s in enabled_sats:
        if s.norad_id not in tle_results:
            continue
        tle_line1, tle_line2 = tle_results[s.norad_id]
        try:
            orb = Orbital(s.name, line1=tle_line1, line2=tle_line2)
            raw_passes = orb.get_next_passes(utc_now, lookahead, lon, lat, alt_km)
            
            above_min = [p for p in raw_passes 
                         if orb.get_observer_look(p[2], lon, lat, alt_km)[1] >= s.min_elevation_deg]
            
            print(f"  {s.name}: {len(raw_passes)} raw passes, {len(above_min)} above {s.min_elevation_deg}° min elevation")
            
            for rise, fall, max_el_time in above_min[:3]:
                az, el = orb.get_observer_look(max_el_time, lon, lat, alt_km)
                print(f"    AOS: {rise.isoformat()}  LOS: {fall.isoformat()}  Max El: {el:.1f}°")
            
            total_passes += len(above_min)
        except Exception as e:
            print(f"  ✗ {s.name}: Prediction FAILED — {e}")
    
    print()

    # 5. API endpoint test
    print(f"[5/5] Summary:")
    if total_passes == 0:
        print("  ✗ No passes predicted in the next {lookahead} hours.")
        print("  Possible reasons:")
        print("    - TLE data may be too old (check TLE age)")
        print("    - min_elevation_deg is too high (try lowering to 5)")
        print("    - Observer location is incorrect")
    else:
        print(f"  ✓ {total_passes} passes predicted! The API should be returning them.")
        print("  If the UI still shows '--:--:--', check browser console for JS errors.")
        print("  You can also test the API directly: curl http://<pi-ip>:5000/api/passes/next")


if __name__ == "__main__":
    main()
