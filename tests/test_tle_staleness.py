"""
Tests for orbital.tle_staleness module.
Mocks config and file system timestamps to verify staleness logic.
"""
import time
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

# We need to mock get_config before importing the module under test,
# so we import at the top and patch consistently.
from orbital import tle_staleness


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tle_config(
    stale_max: float = 72.0,
    warn_after: float = 24.0,
    cache_dir: str = "/tmp/tle_cache",
    tle_filename: str = "weather.tle",
) -> dict:
    """Return a minimal tle config dict."""
    return {
        "cache_dir": cache_dir,
        "tle_filename": tle_filename,
        "stale_tle_max_age_hours": stale_max,
        "warn_if_stale_after_hours": warn_after,
    }


def _mock_config(tle_cfg: dict | None = None) -> MagicMock:
    """Build a mock AppConfig with the given tle section."""
    cfg = MagicMock()
    cfg.tle = tle_cfg or _make_tle_config()
    return cfg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetTleAgeHours:
    """Tests for get_tle_age_hours()."""

    @patch("orbital.tle_staleness.get_config")
    def test_tle_age_returns_none_when_no_cache(self, mock_gc: MagicMock, tmp_path: Path) -> None:
        """When the TLE cache file does not exist, age should be None."""
        cfg = _mock_config(_make_tle_config(cache_dir=str(tmp_path)))
        mock_gc.return_value = cfg

        # File does not exist — should return None
        result = tle_staleness.get_tle_age_hours()
        assert result is None


class TestTleIsUsable:
    """Tests for tle_is_usable()."""

    @patch("orbital.tle_staleness.get_tle_age_hours")
    @patch("orbital.tle_staleness.get_config")
    def test_tle_is_usable_when_fresh(
        self, mock_gc: MagicMock, mock_age: MagicMock
    ) -> None:
        """A 2-hour-old cache should be usable and 'fresh'."""
        mock_gc.return_value = _mock_config()
        mock_age.return_value = 2.0

        usable, reason = tle_staleness.tle_is_usable()

        assert usable is True
        assert reason == "fresh"

    @patch("orbital.tle_staleness.get_tle_age_hours")
    @patch("orbital.tle_staleness.get_config")
    def test_tle_not_usable_when_too_old(
        self, mock_gc: MagicMock, mock_age: MagicMock
    ) -> None:
        """An 80-hour-old cache exceeds the 72 h max and should be expired."""
        mock_gc.return_value = _mock_config()
        mock_age.return_value = 80.0

        usable, reason = tle_staleness.tle_is_usable()

        assert usable is False
        assert reason == "expired"

    @patch("orbital.tle_staleness.get_tle_age_hours")
    @patch("orbital.tle_staleness.get_config")
    def test_tle_usable_but_stale(
        self, mock_gc: MagicMock, mock_age: MagicMock
    ) -> None:
        """A 30-hour-old cache is past the 24 h warn threshold but under 72 h max."""
        mock_gc.return_value = _mock_config()
        mock_age.return_value = 30.0

        usable, reason = tle_staleness.tle_is_usable()

        assert usable is True
        assert reason == "stale"

    @patch("orbital.tle_staleness.get_tle_age_hours")
    @patch("orbital.tle_staleness.get_config")
    def test_tle_missing(
        self, mock_gc: MagicMock, mock_age: MagicMock
    ) -> None:
        """When age is None the cache is missing and not usable."""
        mock_gc.return_value = _mock_config()
        mock_age.return_value = None

        usable, reason = tle_staleness.tle_is_usable()

        assert usable is False
        assert reason == "missing"


class TestTleSalenessBanner:
    """Tests for tle_staleness_banner()."""

    @patch("orbital.tle_staleness.get_tle_age_hours")
    @patch("orbital.tle_staleness.get_config")
    def test_no_banner_when_fresh(
        self, mock_gc: MagicMock, mock_age: MagicMock
    ) -> None:
        """Fresh cache should produce no banner."""
        mock_gc.return_value = _mock_config()
        mock_age.return_value = 2.0

        banner = tle_staleness.tle_staleness_banner()
        assert banner is None

    @patch("orbital.tle_staleness.get_tle_age_hours")
    @patch("orbital.tle_staleness.get_config")
    def test_tle_staleness_banner_warning(
        self, mock_gc: MagicMock, mock_age: MagicMock
    ) -> None:
        """A 30-hour-old cache should produce a warning banner."""
        mock_gc.return_value = _mock_config()
        mock_age.return_value = 30.0

        banner = tle_staleness.tle_staleness_banner()

        assert banner is not None
        assert banner["level"] == "warning"
        assert "30" in banner["message"]

    @patch("orbital.tle_staleness.get_tle_age_hours")
    @patch("orbital.tle_staleness.get_config")
    def test_tle_staleness_banner_error_expired(
        self, mock_gc: MagicMock, mock_age: MagicMock
    ) -> None:
        """An 80-hour-old cache should produce an error banner."""
        mock_gc.return_value = _mock_config()
        mock_age.return_value = 80.0

        banner = tle_staleness.tle_staleness_banner()

        assert banner is not None
        assert banner["level"] == "error"
        assert "expired" in banner["message"].lower()

    @patch("orbital.tle_staleness.get_tle_age_hours")
    @patch("orbital.tle_staleness.get_config")
    def test_tle_staleness_banner_error_missing(
        self, mock_gc: MagicMock, mock_age: MagicMock
    ) -> None:
        """Missing cache should produce an error banner."""
        mock_gc.return_value = _mock_config()
        mock_age.return_value = None

        banner = tle_staleness.tle_staleness_banner()

        assert banner is not None
        assert banner["level"] == "error"
        assert "no tle data" in banner["message"].lower()
