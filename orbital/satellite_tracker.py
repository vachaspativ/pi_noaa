"""
Real-time satellite position and ground-track computation using pyorbital.
Used for live tracking UI overlays and map ground-track lines.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from pyorbital.orbital import Orbital

from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


def get_current_position(
    sat_name: str,
    tle_line1: str,
    tle_line2: str,
) -> dict | None:
    """
    Compute the current position and observer-look angles for a satellite.

    Args:
        sat_name: Human-readable satellite name.
        tle_line1: First TLE line.
        tle_line2: Second TLE line.

    Returns:
        A dict with keys ``azimuth_deg``, ``elevation_deg``, ``range_km``,
        ``latitude``, ``longitude``, ``altitude_km``, and ``timestamp_utc``,
        or ``None`` on failure.
    """
    cfg = get_config().location
    lat: float = cfg["latitude"]
    lon: float = cfg["longitude"]
    alt_km: float = cfg["altitude_m"] / 1000.0

    try:
        orb = Orbital(sat_name, line1=tle_line1, line2=tle_line2)
    except Exception as exc:
        logger.error("Failed to initialise Orbital for %s: %s", sat_name, exc)
        return None

    utc_now = datetime.now(timezone.utc)

    try:
        az, el = orb.get_observer_look(utc_now, lon, lat, alt_km)
        sat_lon, sat_lat, sat_alt = orb.get_lonlatalt(utc_now)
    except Exception as exc:
        logger.error("Position computation failed for %s: %s", sat_name, exc)
        return None

    # Range approximation via slant range from observer-look
    # pyorbital doesn't return range directly from get_observer_look;
    # compute it from the position vectors.
    try:
        pos, vel = orb.get_position(utc_now, normalize=False)
        # pos is in km from Earth centre — compute rough slant range
        import math
        earth_radius_km = 6371.0
        obs_x = (earth_radius_km + alt_km) * math.cos(math.radians(lat)) * math.cos(math.radians(lon))
        obs_y = (earth_radius_km + alt_km) * math.cos(math.radians(lat)) * math.sin(math.radians(lon))
        obs_z = (earth_radius_km + alt_km) * math.sin(math.radians(lat))
        range_km = math.sqrt(
            (pos[0] - obs_x) ** 2 + (pos[1] - obs_y) ** 2 + (pos[2] - obs_z) ** 2
        )
    except Exception:
        range_km = 0.0

    return {
        "azimuth_deg": round(az, 2),
        "elevation_deg": round(el, 2),
        "range_km": round(range_km, 1),
        "latitude": round(sat_lat, 4),
        "longitude": round(sat_lon, 4),
        "altitude_km": round(sat_alt, 1),
        "timestamp_utc": utc_now.isoformat(),
    }


def get_ground_track(
    sat_name: str,
    tle_line1: str,
    tle_line2: str,
    minutes: int = 90,
) -> list[dict]:
    """
    Compute a ground track (list of lat/lon points) for map overlay display.

    The track is centred on the current time, spanning from
    ``now − minutes/2`` to ``now + minutes/2`` at one-minute intervals.

    Args:
        sat_name: Human-readable satellite name.
        tle_line1: First TLE line.
        tle_line2: Second TLE line.
        minutes: Total duration of the ground track in minutes (default 90).

    Returns:
        List of dicts with ``latitude``, ``longitude``, ``altitude_km``, and
        ``timestamp_utc`` keys.  Returns an empty list on failure.
    """
    try:
        orb = Orbital(sat_name, line1=tle_line1, line2=tle_line2)
    except Exception as exc:
        logger.error("Failed to initialise Orbital for %s: %s", sat_name, exc)
        return []

    utc_now = datetime.now(timezone.utc)
    half = minutes / 2.0
    start = utc_now - timedelta(minutes=half)

    track: list[dict] = []

    for offset in range(minutes + 1):
        t = start + timedelta(minutes=offset)
        try:
            sat_lon, sat_lat, sat_alt = orb.get_lonlatalt(t)
            track.append(
                {
                    "latitude": round(sat_lat, 4),
                    "longitude": round(sat_lon, 4),
                    "altitude_km": round(sat_alt, 1),
                    "timestamp_utc": t.isoformat(),
                }
            )
        except Exception as exc:
            logger.warning("Ground track point failed at %s: %s", t, exc)
            continue

    logger.debug("Computed %d ground-track points for %s", len(track), sat_name)
    return track
