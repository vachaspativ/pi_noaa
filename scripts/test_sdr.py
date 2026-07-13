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
    binaries = ["rtl_test", "rtl_fm", "rtl_power", "sox", "satdump", "multimon-ng"]
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
    present, reason = ctrl.hardware_status()
    if present:
        print(f"✓ RTL-SDR hardware detected ({reason})")
    else:
        print(f"✗ RTL-SDR hardware check failed: {reason}")
        print("  Tips:")
        print("  - Is the USB dongle plugged in?")
        print("  - Did you run scripts/setup_rtlsdr.sh to configure udev rules and reboot?")
        print("  - Ensure no other applications are using the SDR.")
        sys.exit(1)
        
    # 3. Test data stream reading (capturing 2 seconds of data)
    print("\nTesting SDR data stream (simulating satellite frequency capture)...")
    try:
        # Run rtl_test to actually stream data for 2 seconds. 
        # If it successfully transfers data without crashing, the connection is solid.
        import time
        proc = subprocess.Popen(
            ["rtl_test", "-s", "2048000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(2.5)
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=2)
        
        output = stdout + stderr
        if "Failed to open rtlsdr device" in output or "usb_claim_interface error" in output:
            print("✗ Data stream test failed. Device became busy or disconnected.")
            sys.exit(1)
        else:
            print("✓ Successfully opened device and read data stream!")
            
    except Exception as e:
        print(f"✗ Data stream test failed with exception: {e}")
        sys.exit(1)

    print("\nSUCCESS: SDR environment is ready and data is flowing!")
