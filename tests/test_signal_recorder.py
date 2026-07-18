"""
Tests for signal_recorder.record_pass orchestration.
All SDR and hardware calls are mocked — no hardware required.
"""
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime, timezone, timedelta

from sdr.signal_recorder import record_pass


def _make_mock_pass(
    satellite_name="NOAA 15",
    frequency_hz=137620000,
    duration_seconds=600,
):
    """Create a mock SatellitePass-like object."""
    now = datetime.now(timezone.utc)
    mock_pass = MagicMock()
    mock_pass.satellite_name = satellite_name
    mock_pass.frequency_hz = frequency_hz
    mock_pass.aos = now - timedelta(seconds=30)
    mock_pass.los = now + timedelta(seconds=duration_seconds)
    return mock_pass


class TestRecordPass:
    """
    The SDRController import is deferred (inside record_pass function body),
    so we patch the class in its source module: sdr.sdr_controller.SDRController.
    """

    @patch("sdr.signal_recorder.time.sleep")
    @patch("sdr.sdr_controller.SDRController.is_hardware_present", return_value=False)
    @patch("sdr.sdr_controller.SDRController.is_recording", new_callable=lambda: property(lambda self: False))
    def test_returns_none_when_hardware_not_present(self, mock_rec, mock_hw, mock_sleep):
        result = record_pass(_make_mock_pass())
        assert result is None

    @patch("sdr.signal_recorder.time.sleep")
    def test_returns_none_when_already_recording(self, mock_sleep):
        from sdr.sdr_controller import SDRController
        sdr = SDRController()
        # Simulate already recording
        sdr._recording = True

        result = record_pass(_make_mock_pass())
        assert result is None

    @patch("sdr.signal_recorder.time.sleep")
    @patch("sdr.sdr_controller.SDRController.start_recording", return_value=False)
    @patch("sdr.sdr_controller.SDRController.is_hardware_present", return_value=True)
    def test_returns_none_when_start_fails(self, mock_hw, mock_start, mock_sleep):
        result = record_pass(_make_mock_pass())
        assert result is None

    @patch("sdr.signal_recorder.time.sleep")
    def test_returns_path_on_success(self, mock_sleep, tmp_path):
        from sdr.sdr_controller import SDRController
        sdr = SDRController()

        # Patch methods directly on the singleton instance
        sdr.is_hardware_present = MagicMock(return_value=True)

        def fake_start(freq, path):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\x00" * 1024)
            sdr._recording = True
            return True

        sdr.start_recording = MagicMock(side_effect=fake_start)
        sdr.stop_recording = MagicMock(side_effect=lambda: setattr(sdr, '_recording', False))

        sat_pass = _make_mock_pass(duration_seconds=1)
        result = record_pass(sat_pass)

        assert result is not None
        assert result.exists()
        assert result.stat().st_size > 0
        sdr.stop_recording.assert_called_once()

    @patch("sdr.signal_recorder.time.sleep", side_effect=KeyboardInterrupt)
    def test_stop_recording_always_called(self, mock_sleep):
        """Even if sleep is interrupted, stop_recording must be called."""
        from sdr.sdr_controller import SDRController
        sdr = SDRController()
        sdr.is_hardware_present = MagicMock(return_value=True)
        sdr.start_recording = MagicMock(return_value=True)
        sdr.stop_recording = MagicMock()

        record_pass(_make_mock_pass())
        sdr.stop_recording.assert_called_once()
