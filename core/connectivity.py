"""
Probes internet reachability with a TCP connection to a known host.
Used by mode_resolver to determine online/offline state.
All probe parameters are read from config.
"""
import socket
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


def is_internet_available(conn_cfg: dict | None = None) -> bool:
    """
    Attempts TCP connection to configured probe host.
    Falls back to a secondary host if primary fails.

    Args:
        conn_cfg: Optional connectivity config dict override (for testing).
                  If None, reads from get_config().

    Returns:
        True if either probe host succeeds.
    """
    if conn_cfg is None:
        conn_cfg = get_config().connectivity

    hosts = [
        (conn_cfg["probe_host"], conn_cfg["probe_port"]),
        (conn_cfg.get("probe_fallback_host", "1.1.1.1"), 53),
    ]
    timeout = conn_cfg.get("probe_timeout_seconds", 5)

    for host, port in hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            logger.debug(f"Internet probe OK via {host}:{port}")
            return True
        except OSError:
            logger.debug(f"Internet probe failed via {host}:{port}")
            continue

    logger.info("Internet is not available (all probes failed)")
    return False
