"""
pi_noaa entry point.
Resolves operating mode, starts all subsystems, launches web server.
"""
import argparse
import uvicorn
from core.config_loader import get_config
from core.logger import setup_logging
from core.mode_resolver import resolve_mode, OperatingMode
from orbital.tle_staleness import tle_is_usable, get_tle_age_hours


def main():
    parser = argparse.ArgumentParser(description="pi_noaa Weather Satellite Station")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--check-hardware", action="store_true")
    parser.add_argument("--check-connectivity", action="store_true")
    parser.add_argument("--scan-wx-radio", action="store_true",
                        help="Scan 162 MHz freqs and print signal strengths")
    args = parser.parse_args()

    cfg = get_config(args.config if args.config != "config.yaml" else None)
    setup_logging(cfg.logging)

    if args.check_hardware:
        from sdr.sdr_controller import SDRController
        present, reason = SDRController().hardware_status()
        print(f"RTL-SDR hardware: {'✓' if present else '✗'} {reason}")
        return

    if args.check_connectivity:
        from core.connectivity import is_internet_available
        online = is_internet_available()
        print(f"Internet: {'✓ Reachable' if online else '✗ Offline'}")
        return

    if args.scan_wx_radio:
        from wx_radio.frequency_scanner import scan_and_report
        scan_and_report()
        return

    # Resolve and print operating mode
    mode = resolve_mode()
    print(f"🛰  pi_noaa starting — mode: [{mode.value.upper()}]")

    # TLE staleness check
    usable, reason = tle_is_usable()
    if not usable:
        print(f"⚠  TLE: {reason}")
        if mode in (OperatingMode.SDR_OFFLINE, OperatingMode.DUAL):
            age = get_tle_age_hours()
            if age is None:
                print("   ✗ No TLE cache. Run with internet first to populate TLE data.")
    else:
        print(f"   TLE: {reason}")

    from api.server import build_app
    app = build_app(mode)
    uvicorn.run(app, host=cfg.server["host"], port=cfg.server["port"])

if __name__ == "__main__":
    main()
