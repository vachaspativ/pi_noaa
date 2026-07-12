"""
Utility to scan NOAA Weather Radio frequencies to find the strongest signal.
Uses rtl_power (subprocess) to measure relative RF power levels.
"""
import subprocess
import tempfile
import csv
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


def scan_frequencies() -> dict[int, float]:
    """
    Scans the configured WX Radio frequencies using rtl_power.
    
    Returns:
        Dictionary mapping frequency (Hz) to signal strength (dBm).
        Higher (less negative) is better.
    """
    cfg = get_config()
    freqs = cfg.noaa_weather_radio.get("frequencies_hz", [])
    dwell_time = cfg.noaa_weather_radio.get("scan_dwell_seconds", 5)
    sdr_idx = cfg.sdr.get("device_index", 0)
    
    if not freqs:
        logger.error("No WX radio frequencies configured")
        return {}
        
    results = {}
    
    # We scan each frequency individually using rtl_power
    for freq in freqs:
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.csv') as tmp:
            cmd = [
                "rtl_power",
                "-f", f"{freq}:{freq}:10k", # Lower:Upper:BinSize
                "-g", "49.6",               # High gain for scanning
                "-i", "1",                  # Integration time 1s
                "-e", f"{dwell_time}s",     # Total run time
                "-d", str(sdr_idx),
                tmp.name
            ]
            
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=dwell_time + 5,
                )
                
                tmp.seek(0)
                reader = csv.reader(tmp)
                max_db = -100.0
                
                # rtl_power CSV format: date, time, hz_low, hz_high, hz_step, samples, dbm...
                for row in reader:
                    if len(row) > 6:
                        try:
                            # Average or max of the bins
                            dbs = [float(x) for x in row[6:] if x.strip()]
                            if dbs:
                                max_db = max(max_db, max(dbs))
                        except ValueError:
                            pass
                            
                results[freq] = max_db
                
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
                logger.error(f"Failed to scan {freq} Hz: {e}")
                results[freq] = -100.0
                
    return results


def get_best_frequency() -> int | None:
    """Scan and return the frequency with the highest signal strength."""
    results = scan_frequencies()
    if not results:
        return None
        
    best_freq = max(results.items(), key=lambda x: x[1])
    # If the "best" is absolute garbage, we might not have an antenna attached
    if best_freq[1] < -60.0:
        logger.warning(f"Best signal is very weak ({best_freq[1]} dBm). Antenna connected?")
        
    return best_freq[0]


def scan_and_report() -> None:
    """CLI utility function: scan and print formatted report."""
    print("📡 Scanning NOAA Weather Radio frequencies...")
    cfg = get_config()
    dwell_time = cfg.noaa_weather_radio.get("scan_dwell_seconds", 5)
    print(f"Dwelling {dwell_time} seconds per frequency.\n")
    
    results = scan_frequencies()
    
    if not results:
        print("✗ Scan failed or no frequencies configured.")
        return
        
    print(f"{'Frequency (MHz)':<20} | {'Signal Strength (dBm)'}")
    print("-" * 45)
    
    for freq, dbm in sorted(results.items()):
        mhz = freq / 1e6
        print(f"{mhz:<20.4f} | {dbm:.1f}")
        
    best_freq = max(results.items(), key=lambda x: x[1])
    print("-" * 45)
    print(f"★ Best frequency: {best_freq[0]/1e6:.4f} MHz ({best_freq[1]:.1f} dBm)")
    print("\nTo use this, set in config.yaml:")
    print("noaa_weather_radio:")
    print(f"  preferred_frequency_hz: {best_freq[0]}")
