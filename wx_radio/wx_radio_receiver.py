"""
Background service that listens to 162 MHz NOAA Weather Radio.
Pipes demodulated audio from rtl_fm directly into multimon-ng to decode SAME alerts in real-time.
"""
import subprocess
import threading
from typing import Callable
from wx_radio.same_decoder import parse_same_string, SAMEAlert
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


class WXRadioReceiver:
    """
    Manages continuous listening to WX Radio.
    Time-shares the SDR hardware — will yield if a satellite pass starts.
    """

    def __init__(self):
        self.cfg = get_config()
        self._rtl_process: subprocess.Popen | None = None
        self._multimon_process: subprocess.Popen | None = None
        self._monitoring = False
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[SAMEAlert], None]] = []
        self._reader_thread: threading.Thread | None = None

    def on_same_alert(self, callback: Callable[[SAMEAlert], None]) -> None:
        """Register a callback for when a SAME alert is decoded."""
        self._callbacks.append(callback)

    def start_monitoring(self, frequency_hz: int) -> bool:
        """
        Start the rtl_fm | multimon-ng pipeline.
        
        Args:
            frequency_hz: Frequency to tune to (e.g. 162400000).
            
        Returns:
            True if started, False if error or already monitoring.
        """
        with self._lock:
            if self._monitoring:
                return False
                
            sdr_cfg = self.cfg.sdr
            
            # WX Radio is NBFM
            rtl_cmd = [
                "rtl_fm",
                "-f", str(frequency_hz),
                "-M", "fm",
                "-s", "22050",
                "-p", str(sdr_cfg.get("ppm_correction", 0)),
                "-E", "dc",
                "-",
            ]
            
            if sdr_cfg.get("gain_mode") == "manual":
                rtl_cmd.extend(["-g", str(sdr_cfg.get("gain_db", 49.6))])
                
            multimon_cmd = [
                "multimon-ng",
                "-t", "raw",
                "-a", "EAS",
                "-"
            ]
            
            try:
                logger.info(f"Starting WX Radio monitor on {frequency_hz / 1e6:.4f} MHz")
                self._rtl_process = subprocess.Popen(
                    rtl_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                self._multimon_process = subprocess.Popen(
                    multimon_cmd,
                    stdin=self._rtl_process.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True, # Decode stdout as string for readline
                    bufsize=1, # Line buffered
                )
                
                self._monitoring = True
                
                # Start background thread to read multimon-ng output
                self._reader_thread = threading.Thread(
                    target=self._read_loop,
                    daemon=True
                )
                self._reader_thread.start()
                
                return True
                
            except (FileNotFoundError, OSError) as e:
                logger.error(f"Failed to start WX Radio receiver: {e}")
                self.stop_monitoring()
                return False

    def stop_monitoring(self) -> None:
        """Gracefully stop the receiver pipeline."""
        with self._lock:
            if not self._monitoring:
                return
                
            logger.info("Stopping WX Radio monitor")
            
            if self._rtl_process:
                try:
                    self._rtl_process.terminate()
                    self._rtl_process.wait(timeout=2)
                except (subprocess.TimeoutExpired, OSError):
                    self._rtl_process.kill()
                self._rtl_process = None
                
            if self._multimon_process:
                try:
                    self._multimon_process.terminate()
                    self._multimon_process.wait(timeout=2)
                except (subprocess.TimeoutExpired, OSError):
                    self._multimon_process.kill()
                self._multimon_process = None
                
            self._monitoring = False
            # Thread will naturally die when stdout closes

    @property
    def is_monitoring(self) -> bool:
        return self._monitoring

    def _read_loop(self) -> None:
        """Background thread that reads stdout from multimon-ng."""
        if not self._multimon_process or not self._multimon_process.stdout:
            return
            
        try:
            # readline() blocks until a newline or EOF
            for line in iter(self._multimon_process.stdout.readline, ""):
                if not line:
                    break
                self._process_output_line(line.strip())
        except ValueError:
            pass # Handle closed file descriptor

    def _process_output_line(self, line: str) -> None:
        """Check if line contains an EAS alert and parse it."""
        if "EAS:" in line or "ZCZC-" in line:
            alert = parse_same_string(line)
            if alert:
                logger.warning(
                    f"⚠️ DECODED WX RADIO ALERT: {alert.event_name} "
                    f"for {len(alert.fips_codes)} areas"
                )
                for cb in self._callbacks:
                    try:
                        cb(alert)
                    except Exception as e:
                        logger.error(f"WX Radio callback error: {e}")
