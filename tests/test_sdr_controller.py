"""
Tests for SDRController singleton, process management, and recording logic.
All subprocess calls are mocked — no SDR hardware required.
"""
import subprocess
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

from sdr.sdr_controller import SDRController


class TestSDRControllerSingleton:
    """Verify that SDRController is a singleton."""

    def test_same_instance_returned(self):
        sdr1 = SDRController()
        sdr2 = SDRController()
        assert sdr1 is sdr2

    def test_is_recording_shared_across_references(self):
        sdr1 = SDRController()
        sdr2 = SDRController()

        assert sdr1.is_recording is False
        assert sdr2.is_recording is False

        # Mutate via sdr1, read via sdr2
        sdr1._recording = True
        assert sdr2.is_recording is True


class TestHardwareStatus:
    """Test hardware detection with mocked subprocess."""

    @patch("sdr.sdr_controller.subprocess.run")
    def test_hardware_present_rc0(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        sdr = SDRController()
        present, msg = sdr.hardware_status()
        assert present is True
        assert "available" in msg.lower()

    @patch("sdr.sdr_controller.subprocess.run")
    def test_hardware_not_found(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="No supported devices found",
            stderr="",
        )
        sdr = SDRController()
        present, msg = sdr.hardware_status()
        assert present is False
        assert "not found" in msg.lower()

    @patch("sdr.sdr_controller.subprocess.run", side_effect=FileNotFoundError)
    def test_rtl_test_not_installed(self, mock_run):
        sdr = SDRController()
        present, msg = sdr.hardware_status()
        assert present is False
        assert "not installed" in msg.lower()

    @patch("sdr.sdr_controller.subprocess.run", side_effect=subprocess.TimeoutExpired("rtl_test", 2))
    def test_timeout_means_present(self, mock_run):
        sdr = SDRController()
        present, msg = sdr.hardware_status()
        assert present is True


class TestStartRecording:
    """Test recording start with mocked subprocesses."""

    @patch("sdr.sdr_controller.time.sleep")
    @patch("sdr.sdr_controller.subprocess.Popen")
    def test_successful_start(self, mock_popen, mock_sleep, tmp_path):
        """Both processes stay alive → recording should succeed."""
        rtl_proc = MagicMock()
        rtl_proc.poll.return_value = None  # still alive
        rtl_proc.stdout = MagicMock()

        sox_proc = MagicMock()
        sox_proc.poll.return_value = None  # still alive

        mock_popen.side_effect = [rtl_proc, sox_proc]

        sdr = SDRController()
        output = tmp_path / "test.wav"
        result = sdr.start_recording(137620000, output)

        assert result is True
        assert sdr.is_recording is True
        assert sdr.last_error is None

    @patch("sdr.sdr_controller.time.sleep")
    @patch("sdr.sdr_controller.subprocess.Popen")
    def test_rtl_fm_exits_immediately(self, mock_popen, mock_sleep, tmp_path):
        """rtl_fm exits immediately (device missing) → should return False."""
        rtl_proc = MagicMock()
        rtl_proc.poll.return_value = 1  # exited
        rtl_proc.stderr = MagicMock()
        rtl_proc.stderr.read.return_value = b"No supported devices found"
        rtl_proc.stderr.closed = False
        rtl_proc.stdout = MagicMock()
        rtl_proc.stdout.closed = False

        sox_proc = MagicMock()
        sox_proc.stderr = MagicMock()
        sox_proc.stderr.read.return_value = b""
        sox_proc.stderr.closed = False

        mock_popen.side_effect = [rtl_proc, sox_proc]

        sdr = SDRController()
        output = tmp_path / "test.wav"
        result = sdr.start_recording(137620000, output)

        assert result is False
        assert sdr.is_recording is False
        assert sdr.last_error is not None
        assert "rtl_fm exited" in sdr.last_error

    @patch("sdr.sdr_controller.subprocess.Popen", side_effect=FileNotFoundError("rtl_fm"))
    def test_binary_not_found(self, mock_popen, tmp_path):
        """rtl_fm binary not installed → should return False."""
        sdr = SDRController()
        output = tmp_path / "test.wav"
        result = sdr.start_recording(137620000, output)

        assert result is False
        assert sdr.is_recording is False
        assert "not found" in sdr.last_error.lower()

    @patch("sdr.sdr_controller.time.sleep")
    @patch("sdr.sdr_controller.subprocess.Popen")
    def test_already_recording_returns_false(self, mock_popen, mock_sleep, tmp_path):
        """Calling start_recording while already recording → returns False."""
        rtl_proc = MagicMock()
        rtl_proc.poll.return_value = None
        rtl_proc.stdout = MagicMock()

        sox_proc = MagicMock()
        sox_proc.poll.return_value = None

        mock_popen.side_effect = [rtl_proc, sox_proc]

        sdr = SDRController()
        output = tmp_path / "test.wav"
        sdr.start_recording(137620000, output)

        # Second call should fail
        result = sdr.start_recording(137620000, tmp_path / "test2.wav")
        assert result is False


class TestStopRecording:
    """Test recording stop and cleanup."""

    @patch("sdr.sdr_controller.time.sleep")
    @patch("sdr.sdr_controller.subprocess.Popen")
    def test_stop_sets_not_recording(self, mock_popen, mock_sleep, tmp_path):
        rtl_proc = MagicMock()
        rtl_proc.poll.return_value = None
        rtl_proc.stdout = MagicMock()
        rtl_proc.stdout.closed = False
        rtl_proc.stderr = MagicMock()
        rtl_proc.stderr.read.return_value = b""
        rtl_proc.stderr.closed = False

        sox_proc = MagicMock()
        sox_proc.poll.return_value = None
        sox_proc.stderr = MagicMock()
        sox_proc.stderr.read.return_value = b""
        sox_proc.stderr.closed = False

        mock_popen.side_effect = [rtl_proc, sox_proc]

        sdr = SDRController()
        sdr.start_recording(137620000, tmp_path / "test.wav")
        assert sdr.is_recording is True

        sdr.stop_recording()
        assert sdr.is_recording is False

    @patch("sdr.sdr_controller.time.sleep")
    @patch("sdr.sdr_controller.subprocess.Popen")
    def test_cleanup_closes_stdout_pipe(self, mock_popen, mock_sleep, tmp_path):
        """Verify that rtl_fm stdout pipe is closed so sox sees EOF."""
        rtl_proc = MagicMock()
        rtl_proc.poll.return_value = None
        rtl_proc.stdout = MagicMock()
        rtl_proc.stdout.closed = False
        rtl_proc.stderr = MagicMock()
        rtl_proc.stderr.read.return_value = b""
        rtl_proc.stderr.closed = False

        sox_proc = MagicMock()
        sox_proc.poll.return_value = None
        sox_proc.stderr = MagicMock()
        sox_proc.stderr.read.return_value = b""
        sox_proc.stderr.closed = False

        mock_popen.side_effect = [rtl_proc, sox_proc]

        sdr = SDRController()
        sdr.start_recording(137620000, tmp_path / "test.wav")
        sdr.stop_recording()

        # Verify stdout pipe was closed
        rtl_proc.stdout.close.assert_called()

    def test_stop_when_not_recording_is_noop(self):
        sdr = SDRController()
        sdr.stop_recording()  # Should not raise
        assert sdr.is_recording is False
