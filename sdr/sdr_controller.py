"""
Manages RTL-SDR hardware lifecycle.
Records satellite passes to WAV files for APT decoding.
Uses rtl_fm (subprocess) for robust FM demodulation.
"""
import subprocess
import threading
from pathlib import Path
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


class SDRController:
    """
    Controls the RTL-SDR dongle for recording satellite signals.
    Thread-safe — uses a lock to prevent simultaneous recordings.
    """

    def __init__(self):
        self.cfg = get_config()
        self._process: subprocess.Popen | None = None
        self._sox_process: subprocess.Popen | None = None
        self._recording = False
        self._lock = threading.Lock()

    def hardware_status(self) -> tuple[bool, str]:
        """Returns (is_available, status_message)."""
        import time
        try:
            # Start rtl_test as a background process
            proc = subprocess.Popen(
                ["rtl_test", "-t"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Wait a short duration to see if it starts streaming or exits with error
            time.sleep(1.5)
            
            # Check if it has exited
            if proc.poll() is None:
                # Still running means it successfully claimed the interface and started testing!
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return True, "SDR is available and ready."
            
            # It exited, meaning there was an error
            stdout, stderr = proc.communicate()
            output = stdout + stderr
            
            # Check if device was found but we couldn't open it (busy or blocked)
            if "usb_claim_interface error" in output or "Failed to open rtlsdr device" in output:
                return False, "SDR is connected but busy (accessed by another application or blocked by TV tuner driver)."
            
            if "No supported devices found" in output:
                return False, "SDR hardware not found."
                
            # Keep only the first few non-empty lines for cleaner logging/output
            clean_output = " ".join([line.strip() for line in output.splitlines() if line.strip()][-2:])
            return False, f"SDR hardware test failed: {clean_output}"
            
        except FileNotFoundError:
            return False, "SDR utilities (rtl_test) not installed."
        except OSError:
            return False, "SDR hardware test execution failed."

    def is_hardware_present(self) -> bool:
        """Quick check — tries to open device via rtl_test."""
        return self.hardware_status()[0]

    def start_recording(self, frequency_hz: int, output_path: Path) -> bool:
        """
        Launch rtl_fm to record signal to WAV via sox.

        Args:
            frequency_hz: Frequency to tune to in Hz.
            output_path: Path to write the output WAV file.

        Returns:
            True if recording started, False if already recording or error.
        """
        with self._lock:
            if self._recording:
                logger.warning("Already recording — skipping start request")
                return False

            sdr_cfg = self.cfg.sdr
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            rtl_cmd = [
                "rtl_fm",
                "-f", str(frequency_hz),
                "-s", "48000",
                "-r", "48000",
                "-d", str(sdr_cfg["device_index"]),
                "-p", str(sdr_cfg["ppm_correction"]),
                "-A", "fast",
                "-E", "dc",
                "-",
            ]

            if sdr_cfg.get("gain_mode") == "manual":
                rtl_cmd.extend(["-g", str(sdr_cfg.get("gain_db", 49.6))])

            sox_cmd = [
                "sox",
                "-t", "raw",
                "-r", "48000",
                "-es", "-b16", "-c1", "-V1",
                "-", str(output_path),
            ]

            try:
                logger.info(
                    f"Starting SDR recording: {frequency_hz / 1e6:.4f} MHz → {output_path}"
                )
                self._process = subprocess.Popen(
                    rtl_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                self._sox_process = subprocess.Popen(
                    sox_cmd,
                    stdin=self._process.stdout,
                    stderr=subprocess.DEVNULL,
                )
                self._recording = True
                return True
            except (FileNotFoundError, OSError) as e:
                logger.error(f"Failed to start SDR recording: {e}")
                self._cleanup_processes()
                return False

    def stop_recording(self) -> None:
        """Gracefully stop rtl_fm and sox."""
        with self._lock:
            if not self._recording:
                return
            self._cleanup_processes()
            self._recording = False
            logger.info("SDR recording stopped")

    def _cleanup_processes(self) -> None:
        """Terminate running subprocesses."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                self._process.kill()
            self._process = None

        if self._sox_process:
            try:
                self._sox_process.wait(timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                self._sox_process.kill()
            self._sox_process = None

    @property
    def is_recording(self) -> bool:
        """Whether the SDR is currently recording."""
        return self._recording
