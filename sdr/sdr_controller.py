"""
Manages RTL-SDR hardware lifecycle.
Records satellite passes to WAV files for APT decoding.
Uses rtl_fm (subprocess) for robust FM demodulation.
"""
import subprocess
import threading
import time
from pathlib import Path
from core.config_loader import get_config
from core.logger import get_logger

logger = get_logger(__name__)


class SDRController:
    """
    Controls the RTL-SDR dongle for recording satellite signals.
    Thread-safe — uses a lock to prevent simultaneous recordings.

    Singleton: all callers receive the same instance so that
    recording state (is_recording, _process handles) is shared
    across the status API, signal_recorder, and orchestrator.
    """

    _instance = None
    _init_done = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if SDRController._init_done:
            return
        self.cfg = get_config()
        self._process: subprocess.Popen | None = None
        self._sox_process: subprocess.Popen | None = None
        self._recording = False
        self._lock = threading.Lock()
        self._last_error: str | None = None
        SDRController._init_done = True

    def hardware_status(self) -> tuple[bool, str]:
        """Returns (is_available, status_message)."""
        try:
            # R820T tuners exit immediately with code 0.
            # E4000 tuners run forever and will time out (which also implies success).
            # Missing or busy devices exit immediately with a non-zero code.
            result = subprocess.run(
                ["rtl_test", "-t"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if result.returncode == 0:
                return True, "SDR is available and ready."
            
            output = result.stdout + result.stderr
            return self._parse_rtl_test_error(output)
            
        except subprocess.TimeoutExpired:
            # If it timed out, it means the device successfully opened and was running the benchmark
            return True, "SDR is available and ready."
        except FileNotFoundError:
            return False, "SDR utilities (rtl_test) not installed."
        except OSError:
            return False, "SDR hardware test execution failed."

    def _parse_rtl_test_error(self, output: str) -> tuple[bool, str]:
        # Check if device was found but we couldn't open it (busy or blocked)
        if "usb_claim_interface error" in output or "Failed to open rtlsdr device" in output:
            return False, "SDR is connected but busy (accessed by another application or blocked by TV tuner driver)."
        
        if "No supported devices found" in output:
            return False, "SDR hardware not found."
            
        # Keep only the first few non-empty lines for cleaner logging/output
        clean_output = " ".join([line.strip() for line in output.splitlines() if line.strip()][-2:])
        return False, f"SDR hardware test failed: {clean_output}"

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

            self._last_error = None
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
                logger.debug(f"rtl_fm command: {' '.join(rtl_cmd)}")
                logger.debug(f"sox command: {' '.join(sox_cmd)}")

                self._process = subprocess.Popen(
                    rtl_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self._sox_process = subprocess.Popen(
                    sox_cmd,
                    stdin=self._process.stdout,
                    stderr=subprocess.PIPE,
                )

                # Give rtl_fm a moment to start, then verify it's alive.
                # If the device is missing or busy, rtl_fm exits immediately.
                time.sleep(1.5)
                rtl_poll = self._process.poll()
                if rtl_poll is not None:
                    # rtl_fm already exited — capture the error
                    stderr_out = self._process.stderr.read().decode(errors="replace").strip()
                    self._last_error = f"rtl_fm exited immediately (code {rtl_poll}): {stderr_out}"
                    logger.error(f"SDR recording failed to start — {self._last_error}")
                    self._cleanup_processes()
                    return False

                sox_poll = self._sox_process.poll()
                if sox_poll is not None:
                    stderr_out = self._sox_process.stderr.read().decode(errors="replace").strip()
                    self._last_error = f"sox exited immediately (code {sox_poll}): {stderr_out}"
                    logger.error(f"SDR recording failed to start — {self._last_error}")
                    self._cleanup_processes()
                    return False

                self._recording = True
                logger.info("SDR recording processes launched and verified running")
                return True
            except FileNotFoundError as e:
                self._last_error = f"Binary not found: {e}"
                logger.error(f"Failed to start SDR recording: {self._last_error}")
                self._cleanup_processes()
                return False
            except OSError as e:
                self._last_error = f"OS error launching recording: {e}"
                logger.error(f"Failed to start SDR recording: {self._last_error}")
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
        """Terminate running subprocesses and close pipes cleanly."""
        # Step 1: Terminate rtl_fm
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                self._process.kill()
                try:
                    self._process.wait(timeout=2)
                except (subprocess.TimeoutExpired, OSError):
                    pass

            # Step 2: Close rtl_fm's stdout pipe so sox sees EOF and
            # can finalize the WAV header before exiting.
            try:
                if self._process.stdout and not self._process.stdout.closed:
                    self._process.stdout.close()
            except OSError:
                pass

            # Log any stderr from rtl_fm for debugging
            try:
                if self._process.stderr and not self._process.stderr.closed:
                    err = self._process.stderr.read().decode(errors="replace").strip()
                    if err:
                        logger.debug(f"rtl_fm stderr: {err}")
                    self._process.stderr.close()
            except OSError:
                pass

            self._process = None

        # Step 3: Give sox a moment to flush + finalize the WAV, then terminate
        if self._sox_process:
            try:
                # Wait a short period for sox to finish writing after EOF
                self._sox_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("sox did not exit after rtl_fm EOF — terminating")
                self._sox_process.terminate()
                try:
                    self._sox_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._sox_process.kill()
                    try:
                        self._sox_process.wait(timeout=2)
                    except (subprocess.TimeoutExpired, OSError):
                        pass
            except OSError:
                pass

            # Log any stderr from sox
            try:
                if self._sox_process.stderr and not self._sox_process.stderr.closed:
                    err = self._sox_process.stderr.read().decode(errors="replace").strip()
                    if err:
                        logger.debug(f"sox stderr: {err}")
                    self._sox_process.stderr.close()
            except OSError:
                pass

            self._sox_process = None

    @property
    def is_recording(self) -> bool:
        """Whether the SDR is currently recording."""
        return self._recording

    @property
    def last_error(self) -> str | None:
        """Last error message from a failed recording attempt."""
        return self._last_error
