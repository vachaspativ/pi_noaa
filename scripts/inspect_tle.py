#!/usr/bin/env python3
"""
Quick diagnostic to inspect what is actually inside the TLE cache file.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config_loader import get_config

cfg = get_config()
tle_cfg = cfg.tle
cache_path = Path(tle_cfg["cache_dir"]) / tle_cfg["tle_filename"]

if not cache_path.exists():
    print(f"TLE file not found: {cache_path}")
    sys.exit(1)

lines = cache_path.read_text(encoding="utf-8").strip().splitlines()

print(f"=== TLE Cache Inspector ===")
print(f"File: {cache_path}")
print(f"Total lines: {len(lines)}")
print(f"File size: {cache_path.stat().st_size} bytes")
print()

# Show first 15 lines to understand format
print("--- First 15 lines ---")
for i, line in enumerate(lines[:15]):
    print(f"  [{i:3d}] {repr(line)}")
print()

# Find all NORAD IDs present
print("--- All NORAD IDs found in file ---")
norad_ids = []
for i, line in enumerate(lines):
    if line.startswith("1 "):
        cat_field = line[2:7].strip()
        # Also grab the name from the line before if it exists
        name = lines[i-1].strip() if i > 0 and not lines[i-1].startswith(("1 ", "2 ")) else "?"
        norad_ids.append((cat_field, name))

if norad_ids:
    for nid, name in norad_ids:
        print(f"  NORAD {nid:>6s}  →  {name}")
else:
    print("  No TLE line-1 entries found! The file may not be in TLE format.")
    print()
    print("--- Full file content (first 500 chars) ---")
    print(cache_path.read_text(encoding="utf-8")[:500])

print()
print(f"Looking for: NOAA 15 (25338), NOAA 18 (28654), NOAA 19 (33591)")
for target_name, target_id in [("NOAA 15", "25338"), ("NOAA 18", "28654"), ("NOAA 19", "33591")]:
    found = any(nid == target_id for nid, _ in norad_ids)
    print(f"  {target_name} ({target_id}): {'✓ FOUND' if found else '✗ NOT FOUND'}")
