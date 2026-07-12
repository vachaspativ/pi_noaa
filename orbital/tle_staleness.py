"""
Checks TLE cache age and reports staleness for UI banners and scheduler logic.
Thresholds come from the config.yaml ``tle`` section.
"""
import time
from pathlib import Path

from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


def _get_cache_path() -> Path:
    """Return the full path to the cached TLE file."""
    cfg = get_config().tle
    return Path(cfg["cache_dir"]) / cfg["tle_filename"]


def get_tle_age_hours() -> float | None:
    """
    Return the age of the cached TLE file in hours based on its mtime.

    Returns:
        Age in fractional hours, or ``None`` if the cache file does not exist.
    """
    cache_path = _get_cache_path()
    if not cache_path.exists():
        logger.debug("TLE cache does not exist at %s", cache_path)
        return None

    try:
        mtime = cache_path.stat().st_mtime
        age_seconds = time.time() - mtime
        age_hours = age_seconds / 3600.0
        logger.debug("TLE cache age: %.1f hours", age_hours)
        return age_hours
    except OSError as exc:
        logger.error("Could not stat TLE cache: %s", exc)
        return None


def tle_is_usable() -> tuple[bool, str]:
    """
    Determine whether the cached TLE data is still usable.

    Decision matrix (all thresholds from config):

    * Age ≤ ``warn_if_stale_after_hours`` → usable, "fresh"
    * ``warn_if_stale_after_hours`` < age ≤ ``stale_tle_max_age_hours`` → usable, "stale"
    * Age > ``stale_tle_max_age_hours`` → **not** usable, "expired"
    * No cache file → **not** usable, "missing"

    Returns:
        A ``(usable, reason)`` tuple.
    """
    cfg = get_config().tle
    max_age: float = cfg["stale_tle_max_age_hours"]
    warn_age: float = cfg["warn_if_stale_after_hours"]

    age = get_tle_age_hours()

    if age is None:
        return False, "missing"

    if age > max_age:
        logger.warning("TLE cache expired (%.1f h > %.1f h max)", age, max_age)
        return False, "expired"

    if age > warn_age:
        logger.info("TLE cache is stale (%.1f h > %.1f h warn threshold)", age, warn_age)
        return True, "stale"

    return True, "fresh"


def tle_staleness_banner() -> dict | None:
    """
    Return a UI-ready banner dict if the TLE data deserves a user notification.

    Banner levels:

    * ``warning`` — cache is stale but still usable
    * ``error`` — cache is expired or missing

    Returns:
        ``{"level": str, "message": str}`` or ``None`` when the cache is fresh.
    """
    usable, reason = tle_is_usable()

    if reason == "fresh":
        return None

    age = get_tle_age_hours()

    if reason == "missing":
        return {
            "level": "error",
            "message": (
                "No TLE data cached. Satellite pass predictions are unavailable. "
                "Connect to the internet to download orbital data."
            ),
        }

    if reason == "expired":
        return {
            "level": "error",
            "message": (
                f"TLE data is {age:.0f} hours old and has expired. "
                "Pass predictions may be inaccurate. "
                "Connect to the internet to refresh orbital data."
            ),
        }

    # reason == "stale"
    return {
        "level": "warning",
        "message": (
            f"TLE data is {age:.0f} hours old. "
            "Predictions are still usable but should be refreshed soon."
        ),
    }
