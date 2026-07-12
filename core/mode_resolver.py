"""
Determines the effective operating mode based on hardware availability
and internet reachability. Re-evaluates periodically per config.
Emits mode change events to WebSocket clients.
"""
from enum import Enum
from typing import Callable, Optional
from core.config_loader import get_config
from core.connectivity import is_internet_available
from core.logger import get_logger

logger = get_logger(__name__)


class OperatingMode(str, Enum):
    """The four operating states of pi_noaa."""
    DUAL = "dual"                # SDR satellite + NWS API (both available)
    SDR_OFFLINE = "sdr_offline"  # SDR satellite + 162MHz WX Radio (no internet)
    API_ONLY = "api_only"        # NWS API alerts only (no SDR hardware)
    DEGRADED = "degraded"        # SQLite cache only (no hardware, no internet)


_current_mode: Optional[OperatingMode] = None
_mode_change_callbacks: list[Callable] = []


def _check_sdr_hardware() -> bool:
    """Check if RTL-SDR hardware is present without importing sdr module at module level."""
    import subprocess
    try:
        result = subprocess.run(
            ["rtl_test", "-t"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def resolve_mode(
    force_mode: Optional[str] = None,
    has_hardware: Optional[bool] = None,
    has_internet: Optional[bool] = None,
) -> OperatingMode:
    """
    Runs the decision tree and returns the effective OperatingMode.
    Also fires callbacks if mode changed since last call.

    Args:
        force_mode: Override from config or caller. If not "auto", uses directly.
        has_hardware: Override hardware detection (for testing).
        has_internet: Override internet detection (for testing).

    Returns:
        The resolved OperatingMode.
    """
    global _current_mode
    cfg = get_config()
    forced = force_mode or cfg.mode["primary"]

    if forced != "auto":
        try:
            mode = OperatingMode(forced)
        except ValueError:
            logger.warning(f"Invalid mode '{forced}' in config, falling back to auto")
            forced = "auto"

    if forced == "auto":
        hw = has_hardware if has_hardware is not None else _check_sdr_hardware()
        inet = has_internet if has_internet is not None else is_internet_available()

        if hw and inet:
            mode = OperatingMode.DUAL
        elif hw and not inet:
            mode = OperatingMode.SDR_OFFLINE
        elif not hw and inet:
            mode = OperatingMode.API_ONLY
        else:
            mode = OperatingMode.DEGRADED

    if mode != _current_mode:
        old = _current_mode
        _current_mode = mode
        logger.info(f"Operating mode: {old} → {mode.value}")
        for cb in _mode_change_callbacks:
            try:
                cb(mode)
            except Exception as e:
                logger.error(f"Mode change callback error: {e}")

    return mode


def get_current_mode() -> Optional[OperatingMode]:
    """Return the last resolved mode, or None if not yet resolved."""
    return _current_mode


def on_mode_change(callback: Callable[[OperatingMode], None]) -> None:
    """Register a callback fired when operating mode changes."""
    _mode_change_callbacks.append(callback)


def reset_mode_state() -> None:
    """Reset internal state (for testing)."""
    global _current_mode
    _current_mode = None
    _mode_change_callbacks.clear()
