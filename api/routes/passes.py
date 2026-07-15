"""
Passes API routes — satellite pass predictions.
"""
from fastapi import APIRouter

router = APIRouter(tags=["passes"])


@router.get("/passes")
async def get_passes():
    """Return upcoming satellite passes for the next lookahead period."""
    try:
        from orbital.pass_predictor import get_upcoming_passes
        passes = get_upcoming_passes()
        return [
            {
                "satellite_name": p.satellite_name,
                "norad_id": p.norad_id,
                "frequency_hz": p.frequency_hz,
                "aos": p.aos.isoformat() if p.aos else None,
                "los": p.los.isoformat() if p.los else None,
                "max_elevation_deg": p.max_elevation_deg,
                "aos_azimuth_deg": p.aos_azimuth_deg,
                "max_el_azimuth_deg": p.max_el_azimuth_deg,
                "los_azimuth_deg": p.los_azimuth_deg,
                "duration_seconds": p.duration_seconds,
                "is_northbound": p.is_northbound,
            }
            for p in passes
        ]
    except Exception as e:
        return {"error": str(e), "passes": []}


@router.get("/passes/next")
async def get_next_pass():
    """Return only the next upcoming satellite pass."""
    try:
        from orbital.pass_predictor import get_next_pass
        p = get_next_pass()
        if p is None:
            return {"pass": None, "message": "No upcoming passes found"}
        return {
            "pass": {
                "satellite_name": p.satellite_name,
                "norad_id": p.norad_id,
                "frequency_hz": p.frequency_hz,
                "aos": p.aos.isoformat() if p.aos else None,
                "los": p.los.isoformat() if p.los else None,
                "max_elevation_deg": p.max_elevation_deg,
                "duration_seconds": p.duration_seconds,
            }
        }
    except Exception as e:
        return {"error": str(e), "pass": None}


@router.get("/passes/{norad_id}/position")
async def get_satellite_position(norad_id: int):
    """Return live position (az/el) of a satellite during its pass."""
    try:
        from orbital.tle_fetcher import get_tle_for_satellite
        from orbital.satellite_tracker import get_current_position
        from core.config_loader import get_config

        cfg = get_config()
        sat = next(
            (s for s in cfg.satellites if s.norad_id == norad_id), None
        )
        if sat is None:
            return {"error": f"Satellite {norad_id} not found in config"}

        tle = get_tle_for_satellite(norad_id)
        if tle is None:
            return {"error": "No TLE data available for this satellite"}

        position = get_current_position(sat.name, tle[0], tle[1])
        return position
    except Exception as e:
        return {"error": str(e)}
