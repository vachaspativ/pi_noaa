"""
Predicts upcoming satellite passes using pyorbital and cached TLE data.
All prediction parameters come from config.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from pyorbital.orbital import Orbital

from core.config_loader import get_config
from core.logger import get_logger
from orbital.tle_fetcher import get_tle_for_satellite

logger = get_logger(__name__)


@dataclass
class SatellitePass:
    """Predicted satellite pass with geometry and timing details."""

    satellite_name: str
    norad_id: int
    frequency_hz: int
    aos: datetime
    los: datetime
    max_elevation_deg: float
    aos_azimuth_deg: float
    max_el_azimuth_deg: float
    los_azimuth_deg: float
    duration_seconds: float
    is_northbound: bool


def _predict_passes_for_satellite(
    sat_name: str,
    norad_id: int,
    frequency_hz: int,
    tle_line1: str,
    tle_line2: str,
    min_elevation_deg: float,
    lookahead_hours: float,
    lat: float,
    lon: float,
    alt_km: float,
) -> list[SatellitePass]:
    """
    Use pyorbital to compute visible passes for a single satellite.

    Args:
        sat_name: Human-readable satellite name.
        norad_id: NORAD catalog number.
        frequency_hz: Downlink frequency in Hz.
        tle_line1: First TLE line.
        tle_line2: Second TLE line.
        min_elevation_deg: Minimum peak elevation to keep a pass.
        lookahead_hours: How many hours ahead to predict.
        lat: Observer latitude (degrees, north positive).
        lon: Observer longitude (degrees, east positive).
        alt_km: Observer altitude in **kilometres**.

    Returns:
        List of SatellitePass objects, potentially empty.
    """
    try:
        orb = Orbital(sat_name, line1=tle_line1, line2=tle_line2)
    except Exception as exc:
        logger.error("Failed to initialise Orbital for %s: %s", sat_name, exc)
        return []

    utc_now = datetime.now(timezone.utc)
    utc_start = utc_now
    utc_end = utc_now + timedelta(hours=lookahead_hours)

    try:
        raw_passes = orb.get_next_passes(
            utc_start, lookahead_hours, lon, lat, alt_km
        )
    except Exception as exc:
        logger.error("Pass prediction failed for %s: %s", sat_name, exc)
        return []

    results: list[SatellitePass] = []

    for rise_time, fall_time, max_elev_time in raw_passes:
        try:
            # Get observer-look angles at key moments
            aos_az, aos_el = orb.get_observer_look(rise_time, lon, lat, alt_km)
            max_az, max_el = orb.get_observer_look(max_elev_time, lon, lat, alt_km)
            los_az, los_el = orb.get_observer_look(fall_time, lon, lat, alt_km)

            if max_el < min_elevation_deg:
                continue

            duration = (fall_time - rise_time).total_seconds()

            # Determine pass direction: northbound if satellite latitude
            # increases from AOS to LOS.
            try:
                pos_aos = orb.get_lonlatalt(rise_time)
                pos_los = orb.get_lonlatalt(fall_time)
                is_northbound = pos_los[1] > pos_aos[1]
            except Exception:
                is_northbound = False

            # Ensure AOS/LOS are timezone-aware (UTC)
            aos_utc = rise_time if rise_time.tzinfo else rise_time.replace(tzinfo=timezone.utc)
            los_utc = fall_time if fall_time.tzinfo else fall_time.replace(tzinfo=timezone.utc)

            results.append(
                SatellitePass(
                    satellite_name=sat_name,
                    norad_id=norad_id,
                    frequency_hz=frequency_hz,
                    aos=aos_utc,
                    los=los_utc,
                    max_elevation_deg=round(max_el, 1),
                    aos_azimuth_deg=round(aos_az, 1),
                    max_el_azimuth_deg=round(max_az, 1),
                    los_azimuth_deg=round(los_az, 1),
                    duration_seconds=round(duration, 1),
                    is_northbound=is_northbound,
                )
            )
        except Exception as exc:
            logger.warning(
                "Error computing pass geometry for %s at %s: %s",
                sat_name, rise_time, exc,
            )
            continue

    return results


def get_upcoming_passes() -> list[SatellitePass]:
    """
    Predict upcoming passes for all enabled satellites in config.

    Iterates each enabled satellite entry, fetches its cached TLE, predicts
    passes within the configured lookahead window, filters by minimum
    elevation, sorts by AOS time, and caps the result list at
    ``pass_prediction.max_passes_displayed``.

    Returns:
        Sorted list of SatellitePass objects (may be empty).
    """
    cfg = get_config()
    loc = cfg.location
    pred_cfg = cfg.pass_prediction

    lat: float = loc["latitude"]
    lon: float = loc["longitude"]
    alt_km: float = loc["altitude_m"] / 1000.0

    lookahead: float = pred_cfg["lookahead_hours"]
    max_passes: int = pred_cfg["max_passes_displayed"]

    all_passes: list[SatellitePass] = []

    for sat in cfg.satellites:
        if not sat.enabled:
            logger.debug("Skipping disabled satellite: %s", sat.name)
            continue

        tle = get_tle_for_satellite(sat.norad_id)
        if tle is None:
            logger.warning(
                "No TLE available for %s (NORAD %d) — skipping",
                sat.name, sat.norad_id,
            )
            continue

        tle_line1, tle_line2 = tle

        passes = _predict_passes_for_satellite(
            sat_name=sat.name,
            norad_id=sat.norad_id,
            frequency_hz=sat.frequency_hz,
            tle_line1=tle_line1,
            tle_line2=tle_line2,
            min_elevation_deg=sat.min_elevation_deg,
            lookahead_hours=lookahead,
            lat=lat,
            lon=lon,
            alt_km=alt_km,
        )
        all_passes.extend(passes)

    # Sort by AOS ascending and cap the list
    all_passes.sort(key=lambda p: p.aos)
    if len(all_passes) > max_passes:
        all_passes = all_passes[:max_passes]

    logger.info("Predicted %d upcoming passes", len(all_passes))
    return all_passes


def get_next_pass() -> SatellitePass | None:
    """
    Convenience wrapper that returns only the next upcoming pass.

    Returns:
        The earliest SatellitePass, or ``None`` if no passes are predicted.
    """
    passes = get_upcoming_passes()
    return passes[0] if passes else None
