"""
Downloads and caches Two-Line Element (TLE) sets from Celestrak.
All URLs, paths, and TTLs come from config.yaml `tle` section.
"""
import time
from pathlib import Path
from datetime import datetime, timezone

import httpx

from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


def _get_cache_path() -> Path:
    """Return the full path to the cached TLE file."""
    cfg = get_config().tle
    return Path(cfg["cache_dir"]) / cfg["tle_filename"]


def _get_timestamp_path() -> Path:
    """Return the path to the .timestamp sentinel file alongside the TLE cache."""
    return _get_cache_path().with_suffix(".timestamp")


def fetch_and_cache_tles() -> Path | None:
    """
    Download the TLE set from the configured URL and write it to the cache file.

    Creates the cache directory if it does not exist.  A ``.timestamp`` file is
    written alongside the TLE file so other modules can cheaply check freshness.

    Returns:
        Path to the cached TLE file on success, or None on failure.
    """
    cfg = get_config().tle
    url: str = cfg["weather_tle_url"]
    cache_path = _get_cache_path()
    timestamp_path = _get_timestamp_path()

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Fetching TLE data from %s", url)
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()

        tle_text = response.text.strip()
        if not tle_text:
            logger.warning("TLE response was empty — keeping existing cache")
            return cache_path if cache_path.exists() else None

        cache_path.write_text(tle_text, encoding="utf-8")

        # Write a timestamp file so staleness checks are independent of
        # filesystem mtime quirks (e.g. network mounts).
        timestamp_path.write_text(
            datetime.now(timezone.utc).isoformat(), encoding="utf-8"
        )

        logger.info("TLE cache updated: %s (%d bytes)", cache_path, len(tle_text))
        return cache_path

    except httpx.HTTPStatusError as exc:
        logger.error(
            "TLE fetch failed with HTTP %d: %s", exc.response.status_code, exc
        )
    except httpx.RequestError as exc:
        logger.error("TLE fetch request error: %s", exc)
    except OSError as exc:
        logger.error("Failed to write TLE cache: %s", exc)

    return None


def get_tle_for_satellite(norad_id: int) -> tuple[str, str] | None:
    """
    Read the cached TLE file and extract the two TLE lines for *norad_id*.

    The standard 3-line TLE format is::

        NOAA 19
        1 33591U 09005A   ...
        2 33591  ...

    Line-1 begins with ``1 `` and encodes the NORAD catalog number starting at
    column 3 (0-indexed column 2).

    Args:
        norad_id: NORAD catalog number of the satellite.

    Returns:
        A ``(line1, line2)`` tuple, or ``None`` if the cache file does not
        exist or the satellite is not found.
    """
    cache_path = _get_cache_path()

    if not cache_path.exists():
        logger.warning("TLE cache not found at %s — run fetch_and_cache_tles() first", cache_path)
        return None

    try:
        lines = cache_path.read_text(encoding="utf-8").strip().splitlines()
    except OSError as exc:
        logger.error("Failed to read TLE cache: %s", exc)
        return None

    norad_str = str(norad_id)

    # Walk through lines looking for a line-1 that matches the NORAD ID.
    # The NORAD ID occupies columns 2–6 of line 1 (0-indexed).
    for i, line in enumerate(lines):
        if not line.startswith("1 "):
            continue
        # Extract the catalog number field (columns 2-6, stripped).
        cat_field = line[2:7].strip()
        if cat_field == norad_str and i + 1 < len(lines) and lines[i + 1].startswith("2 "):
            logger.debug("Found TLE for NORAD %d", norad_id)
            return lines[i].strip(), lines[i + 1].strip()

    logger.warning("NORAD ID %d not found in TLE cache", norad_id)
    return None
