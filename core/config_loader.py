"""
Loads config.yaml using PyYAML and validates structure with Pydantic.
All modules import get_config() — never parse YAML directly elsewhere.
"""
import os
import yaml
from pathlib import Path
from functools import lru_cache
from pydantic import BaseModel, field_validator
from typing import List, Optional, Any


# Resolve config path relative to project root (directory containing this package)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"

# Allow override via environment variable
CONFIG_PATH = Path(os.environ.get("PI_NOAA_CONFIG", str(_DEFAULT_CONFIG_PATH)))


class SatelliteConfig(BaseModel):
    """Configuration for a single satellite target."""
    name: str
    norad_id: int
    frequency_hz: int
    signal_type: str
    enabled: bool
    min_elevation_deg: float

    @field_validator("frequency_hz")
    @classmethod
    def frequency_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"frequency_hz must be positive, got {v}")
        return v

    @field_validator("min_elevation_deg")
    @classmethod
    def elevation_must_be_valid(cls, v: float) -> float:
        if v < 0 or v > 90:
            raise ValueError(f"min_elevation_deg must be 0-90, got {v}")
        return v


class AppConfig(BaseModel):
    """
    Root configuration model for pi_noaa.
    Every section of config.yaml is represented here.
    """
    location: dict
    mode: dict
    sdr: dict
    satellites: List[SatelliteConfig]
    tle: dict
    pass_prediction: dict
    recording: dict
    apt_decoder: dict
    image: dict
    noaa_weather_radio: dict
    nws_api: dict
    alert_classification: dict
    offline_cache: dict
    connectivity: dict
    map: dict
    geo: dict
    server: dict
    websocket: dict
    storage: dict
    logging: dict
    notifications: dict

    @field_validator("location")
    @classmethod
    def location_must_have_coords(cls, v: dict) -> dict:
        for key in ("latitude", "longitude", "altitude_m"):
            if key not in v:
                raise ValueError(f"location must contain '{key}'")
        return v


class ConfigValidationError(Exception):
    """Raised when config.yaml fails validation."""
    pass


@lru_cache(maxsize=1)
def get_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load and return the singleton config. Cached after first load.

    Args:
        config_path: Override path to config.yaml. If None, uses default.

    Returns:
        Validated AppConfig instance.

    Raises:
        ConfigValidationError: If config file is missing or invalid.
    """
    path = Path(config_path) if config_path else CONFIG_PATH

    if not path.exists():
        raise ConfigValidationError(
            f"Config file not found: {path}\n"
            f"Copy config.yaml.example to config.yaml and edit it."
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Failed to parse config YAML: {e}")

    if raw is None:
        raise ConfigValidationError("Config file is empty")

    try:
        return AppConfig(**raw)
    except Exception as e:
        raise ConfigValidationError(f"Config validation failed: {e}")


def reload_config() -> AppConfig:
    """Force reload config (clears cache). Use after hot-edit of config.yaml."""
    get_config.cache_clear()
    return get_config()
