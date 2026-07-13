#!/usr/bin/env python3
"""
Triage script to test the NOAA Weather Radio (SAME) decoding pipeline in real-time.
Connects to the SDR using the preferred frequency from config.yaml, listens for
messages, and prints any decoded EAS/SAME alerts to the console.
"""
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config_loader import get_config
from wx_radio.wx_radio_receiver import WXRadioReceiver
from sdr.sdr_controller import SDRController


def main():
    print("=== pi_noaa SDR WX Radio Triage ===")
    
    # 1. Verify hardware is available
    print("\n[1/3] Checking SDR Hardware...")
    ctrl = SDRController()
    present, reason = ctrl.hardware_status()
    if not present:
        print(f"✗ SDR Error: {reason}")
        print("Please resolve hardware issues before triaging.")
        sys.exit(1)
    print("✓ SDR hardware detected and ready.")

    # 2. Load Config
    print("\n[2/3] Loading Configuration...")
    cfg = get_config()
    freq = cfg.noaa_weather_radio.get("preferred_frequency_hz")
    
    if not freq:
        print("✗ No preferred_frequency_hz found in config.yaml under noaa_weather_radio.")
        print("Please run 'python main.py --scan-wx-radio' and add the best frequency to config.yaml.")
        sys.exit(1)
        
    print(f"✓ Configuration loaded. Target Frequency: {freq / 1e6:.4f} MHz")

    # 3. Start WX Radio Receiver
    print("\n[3/3] Starting SDR stream and decoder...")
    receiver = WXRadioReceiver()
    
    def on_alert_received(alert):
        print("\n" + "="*50)
        print("🔔 NEW MESSAGE DECODED!")
        print("="*50)
        print(f"Event:       {alert.event_name} ({alert.event})")
        print(f"Significance:{alert.significance}")
        print(f"FIPS Codes:  {', '.join(alert.fips_codes)}")
        print(f"Issued by:   {alert.originator}")
        print(f"Expires:     {alert.expires_at}")
        print("="*50 + "\n")
        print(f"Listening on {freq / 1e6:.4f} MHz for more messages... (Press Ctrl+C to stop)")

    receiver.on_same_alert(on_alert_received)
    
    if not receiver.start_monitoring(freq):
        print("✗ Failed to start the WX Radio receiver.")
        sys.exit(1)
        
    print(f"✓ Receiver pipeline active!")
    print(f"\nListening on {freq / 1e6:.4f} MHz...")
    print("Note: NOAA Weather Radio constantly broadcasts voice audio, but digital SAME messages")
    print("are only transmitted when an alert is issued (or during Weekly Tests).")
    print("Waiting for messages... (Press Ctrl+C to stop)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping receiver...")
        receiver.stop_monitoring()
        print("Done.")

if __name__ == "__main__":
    main()
