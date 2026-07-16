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

    After fetching the group TLE, checks whether each enabled satellite's
    NORAD ID is present. Any missing satellites are individually fetched
    from Celestrak by catalog number and appended to the cache.

    Returns:
        Path to the cached TLE file on success, or None on failure.
    """
    cfg_root = get_config()
    cfg = cfg_root.tle
    url: str = cfg["weather_tle_url"]
    cache_path = _get_cache_path()
    timestamp_path = _get_timestamp_path()

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # --- Step 1: Fetch the main group TLE ---
        logger.debug("[TLE API] Connecting to fetch TLE data from: %s", url)
        logger.info("Fetching TLE data from %s", url)
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)

            logger.debug("[TLE API] Response received - Status: %s, Bytes: %s", response.status_code, len(response.content))
            response.raise_for_status()

        tle_text = response.text.strip()
        if not tle_text:
            logger.warning("TLE response was empty — keeping existing cache")
            return cache_path if cache_path.exists() else None

        # --- Step 2: Check for missing satellites and fetch individually ---
        enabled_norad_ids = [
            s.norad_id for s in cfg_root.satellites if s.enabled
        ]

        missing_ids = []
        for norad_id in enabled_norad_ids:
            norad_str = str(norad_id)
            found = False
            for line in tle_text.splitlines():
                if line.startswith("1 ") and line[2:7].strip() == norad_str:
                    found = True
                    break
            if not found:
                missing_ids.append(norad_id)

        if missing_ids:
            logger.info(
                "Group TLE missing %d configured satellite(s): %s. Fetching individually...",
                len(missing_ids), missing_ids,
            )
            base_url = "https://celestrak.org/NORAD/elements/gp.php"
            with httpx.Client(timeout=30.0) as client:
                for norad_id in missing_ids:
                    ind_url = f"{base_url}?CATNR={norad_id}&FORMAT=tle"
                    logger.debug("[TLE API] Fetching individual TLE for NORAD %d from: %s", norad_id, ind_url)
                    try:
                        ind_resp = client.get(ind_url)
                        ind_resp.raise_for_status()
                        ind_text = ind_resp.text.strip()
                        if ind_text and "1 " in ind_text:
                            tle_text += "\n" + ind_text
                            logger.info("Fetched TLE for NORAD %d (%d bytes)", norad_id, len(ind_text))
                        else:
                            logger.warning("Empty or invalid TLE response for NORAD %d", norad_id)
                    except httpx.HTTPStatusError as exc:
                        logger.warning("Failed to fetch TLE for NORAD %d: HTTP %d", norad_id, exc.response.status_code)
                    except httpx.RequestError as exc:
                        logger.warning("Request error fetching TLE for NORAD %d: %s", norad_id, exc)

        cache_path.write_text(tle_text, encoding="utf-8")

        # Write a timestamp file so staleness checks are independent of
        # filesystem mtime quirks (e.g. network mounts).
        timestamp_path.write_text(
            datetime.now(timezone.utc).isoformat(), encoding="utf-8"
        )

        logger.debug("[TLE API] Successfully parsed and cached TLE data (%d bytes) to %s", len(tle_text), cache_path)
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
