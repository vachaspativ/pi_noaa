#!/usr/bin/env python3
"""
Test script to verify SDR hardware and required binaries are installed.
"""
import sys
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdr.sdr_controller import SDRController


def check_binary(name: str) -> bool:
    try:
        subprocess.run(["which", name], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


if __name__ == "__main__":
    print("=== pi_noaa SDR & Binary Diagnostic ===\n")
    
    # 1. Check binaries
    binaries = ["rtl_test", "rtl_fm", "rtl_power", "sox", "aptdec", "multimon-ng"]
    all_bins_ok = True
    
    for b in binaries:
        if check_binary(b):
            print(f"✓ Found: {b}")
        else:
            print(f"✗ Missing: {b}")
            all_bins_ok = False
            
    print("")
    
    if not all_bins_ok:
        print("FAIL: Missing required system dependencies. Please run scripts/install_deps.sh")
        sys.exit(1)
        
    # 2. Check hardware
    print("Testing RTL-SDR hardware connection...")
    ctrl = SDRController()
    if ctrl.is_hardware_present():
        print("✓ RTL-SDR hardware detected and functioning")
    else:
        print("✗ RTL-SDR hardware not detected")
        print("  Tips:")
        print("  - Is the USB dongle plugged in?")
        print("  - Did you run scripts/setup_rtlsdr.sh to configure udev rules?")
        print("  - Try running 'rtl_test -t' manually to see the raw error.")
        sys.exit(1)
        
    print("\nSUCCESS: SDR environment is ready!")
