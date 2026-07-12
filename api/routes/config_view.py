"""
API routes for exposing safe configuration values to the frontend UI.
"""
from fastapi import APIRouter
from core.config_loader import get_config

router = APIRouter(tags=["config"])


@router.get("/config/map")
async def get_map_config():
    """Return map configuration for Leaflet.js."""
    cfg = get_config()
    
    # We can just return the map dict directly, it contains no secrets
    map_cfg = dict(cfg.map)
    
    # If no initial center is set, use observer location
    if not map_cfg.get("initial_center_lat"):
        map_cfg["initial_center_lat"] = cfg.location.get("latitude", 39.8283)
    if not map_cfg.get("initial_center_lon"):
        map_cfg["initial_center_lon"] = cfg.location.get("longitude", -98.5795)
        
    # Append the selected tile URL based on provider
    provider = map_cfg.get("tile_provider", "carto_dark")
    if provider == "osm":
        map_cfg["tile_url"] = map_cfg.get("osm_tile_url")
    elif provider == "local":
        map_cfg["tile_url"] = map_cfg.get("local_tile_url")
    elif provider == "svg_fallback":
        map_cfg["tile_url"] = "" # Handled client-side
    else: # carto_dark
        map_cfg["tile_url"] = map_cfg.get("carto_dark_url")
        
    return map_cfg


@router.get("/config/observer")
async def get_observer_config():
    """Return observer location."""
    cfg = get_config()
    return {
        "latitude": cfg.location.get("latitude"),
        "longitude": cfg.location.get("longitude"),
        "altitude_m": cfg.location.get("altitude_m")
    }
