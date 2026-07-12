"""
Centralized structured logging for pi_noaa.
All modules use get_logger(name) — never configure logging directly.
"""
import logging
import logging.handlers
from pathlib import Path
from typing import Optional


_configured = False


class JSONFormatter(logging.Formatter):
    """Simple JSON log formatter for structured log output."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(log_cfg: dict) -> None:
    """
    Configure logging from the logging section of config.yaml.

    Args:
        log_cfg: Dictionary with keys: level, log_dir, log_filename,
                 max_bytes, backup_count, json_format
    """
    global _configured
    if _configured:
        return

    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_dir = Path(log_cfg.get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / log_cfg.get("log_filename", "pi_noaa.log")
    max_bytes = log_cfg.get("max_bytes", 10485760)
    backup_count = log_cfg.get("backup_count", 5)
    use_json = log_cfg.get("json_format", False)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Clear any existing handlers
    root.handlers.clear()

    # Formatter
    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger. Call setup_logging() first to configure output.

    Args:
        name: Logger name, typically __name__ of the calling module.
    """
    return logging.getLogger(name)
