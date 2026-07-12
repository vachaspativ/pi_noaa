#!/usr/bin/env python3
"""
CLI wrapper for scanning NOAA Weather Radio frequencies.
"""
import sys
from pathlib import Path

# Add project root to path so we can import modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config_loader import get_config
from core.logger import setup_logging
from wx_radio.frequency_scanner import scan_and_report

if __name__ == "__main__":
    cfg = get_config()
    setup_logging(cfg.logging)
    scan_and_report()
