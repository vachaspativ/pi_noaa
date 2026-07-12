"""
Tests for orbital.pass_predictor module.
Mocks TLE data and pyorbital to verify filtering, sorting, and config logic.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

import pytest

from orbital.pass_predictor import get_upcoming_passes, SatellitePass


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

# Realistic TLE lines for NOAA 19 (content doesn't matter — pyorbital is mocked)
_TLE_LINE1 = "1 33591U 09005A   25190.50000000  .00000037  00000-0  32136-4 0  9995"
_TLE_LINE2 = "2 33591  99.1930 200.1234 0014000  50.0000 310.0000 14.12345678100000"


def _sat_config(name: str, norad_id: int, enabled: bool = True, min_el: float = 10.0) -> MagicMock:
    """Create a mock SatelliteConfig."""
    sat = MagicMock()
    sat.name = name
    sat.norad_id = norad_id
    sat.frequency_hz = 137100000
    sat.signal_type = "APT"
    sat.enabled = enabled
    sat.min_elevation_deg = min_el
    return sat


def _make_config(satellites: list | None = None) -> MagicMock:
    """Build a full mock AppConfig."""
    cfg = MagicMock()
    cfg.location = {"latitude": 41.88, "longitude": -87.62, "altitude_m": 182}
    cfg.pass_prediction = {
        "lookahead_hours": 24,
        "max_passes_displayed": 10,
        "scheduler_interval_minutes": 60,
    }
    cfg.satellites = satellites or [
        _sat_config("NOAA 19", 33591),
        _sat_config("NOAA 18", 28654),
    ]
    return cfg


def _fake_raw_passes(count: int = 3, start_offset_minutes: int = 30) -> list:
    """Return a list of (rise, fall, max_elev_time) tuples for mocking."""
    base = datetime.now(timezone.utc) + timedelta(minutes=start_offset_minutes)
    passes = []
    for i in range(count):
        rise = base + timedelta(hours=i * 2)
        fall = rise + timedelta(minutes=14)
        max_t = rise + timedelta(minutes=7)
        passes.append((rise, fall, max_t))
    return passes


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetUpcomingPasses:
    """Tests for get_upcoming_passes()."""

    @patch("orbital.pass_predictor.get_tle_for_satellite")
    @patch("orbital.pass_predictor.get_config")
    @patch("orbital.pass_predictor.Orbital")
    def test_get_upcoming_passes_returns_sorted_list(
        self,
        MockOrbital: MagicMock,
        mock_gc: MagicMock,
        mock_tle: MagicMock,
    ) -> None:
        """Passes from multiple satellites should be merged and sorted by AOS."""
        mock_gc.return_value = _make_config()
        mock_tle.return_value = (_TLE_LINE1, _TLE_LINE2)

        # Create two sets of passes with interleaved times
        now = datetime.now(timezone.utc)
        passes_sat1 = [
            (now + timedelta(hours=1), now + timedelta(hours=1, minutes=14), now + timedelta(hours=1, minutes=7)),
            (now + timedelta(hours=5), now + timedelta(hours=5, minutes=14), now + timedelta(hours=5, minutes=7)),
        ]
        passes_sat2 = [
            (now + timedelta(hours=3), now + timedelta(hours=3, minutes=14), now + timedelta(hours=3, minutes=7)),
        ]

        # Mock Orbital instance
        orb_instance = MagicMock()
        orb_instance.get_observer_look.return_value = (180.0, 45.0)
        orb_instance.get_lonlatalt.return_value = (-87.0, 42.0, 850.0)
        # Return different pass sets on successive calls
        orb_instance.get_next_passes.side_effect = [passes_sat1, passes_sat2]
        MockOrbital.return_value = orb_instance

        result = get_upcoming_passes()

        assert len(result) == 3
        # Verify AOS order is ascending
        for i in range(len(result) - 1):
            assert result[i].aos <= result[i + 1].aos

    @patch("orbital.pass_predictor.get_tle_for_satellite")
    @patch("orbital.pass_predictor.get_config")
    @patch("orbital.pass_predictor.Orbital")
    def test_disabled_satellites_skipped(
        self,
        MockOrbital: MagicMock,
        mock_gc: MagicMock,
        mock_tle: MagicMock,
    ) -> None:
        """Disabled satellites should not have passes predicted."""
        sats = [
            _sat_config("NOAA 19", 33591, enabled=True),
            _sat_config("Meteor-M2 3", 57166, enabled=False),
        ]
        mock_gc.return_value = _make_config(satellites=sats)
        mock_tle.return_value = (_TLE_LINE1, _TLE_LINE2)

        now = datetime.now(timezone.utc)
        passes = [
            (now + timedelta(hours=1), now + timedelta(hours=1, minutes=14), now + timedelta(hours=1, minutes=7)),
        ]

        orb_instance = MagicMock()
        orb_instance.get_observer_look.return_value = (180.0, 45.0)
        orb_instance.get_lonlatalt.return_value = (-87.0, 42.0, 850.0)
        orb_instance.get_next_passes.return_value = passes
        MockOrbital.return_value = orb_instance

        result = get_upcoming_passes()

        # get_tle_for_satellite should only be called for the enabled satellite
        assert mock_tle.call_count == 1
        mock_tle.assert_called_once_with(33591)

        # All returned passes should be from the enabled satellite
        for p in result:
            assert p.satellite_name == "NOAA 19"

    @patch("orbital.pass_predictor.get_tle_for_satellite")
    @patch("orbital.pass_predictor.get_config")
    @patch("orbital.pass_predictor.Orbital")
    def test_passes_filtered_by_min_elevation(
        self,
        MockOrbital: MagicMock,
        mock_gc: MagicMock,
        mock_tle: MagicMock,
    ) -> None:
        """Passes whose max elevation is below min_elevation_deg should be excluded."""
        sats = [_sat_config("NOAA 19", 33591, enabled=True, min_el=30.0)]
        mock_gc.return_value = _make_config(satellites=sats)
        mock_tle.return_value = (_TLE_LINE1, _TLE_LINE2)

        now = datetime.now(timezone.utc)
        passes = [
            (now + timedelta(hours=1), now + timedelta(hours=1, minutes=14), now + timedelta(hours=1, minutes=7)),
            (now + timedelta(hours=3), now + timedelta(hours=3, minutes=14), now + timedelta(hours=3, minutes=7)),
            (now + timedelta(hours=5), now + timedelta(hours=5, minutes=14), now + timedelta(hours=5, minutes=7)),
        ]

        orb_instance = MagicMock()
        # Return different max elevations per call:
        # Call pattern for 3 passes: each pass calls get_observer_look 3 times
        # (AOS, MAX, LOS). MAX elevation is the 2nd call.
        elevations = [
            # Pass 1: AOS az/el, MAX az/el (50° > 30° ✓), LOS az/el
            (90.0, 5.0), (180.0, 50.0), (270.0, 5.0),
            # Pass 2: AOS az/el, MAX az/el (15° < 30° ✗), LOS az/el
            (90.0, 5.0), (180.0, 15.0), (270.0, 5.0),
            # Pass 3: AOS az/el, MAX az/el (65° > 30° ✓), LOS az/el
            (90.0, 5.0), (180.0, 65.0), (270.0, 5.0),
        ]
        orb_instance.get_observer_look.side_effect = elevations
        orb_instance.get_lonlatalt.return_value = (-87.0, 42.0, 850.0)
        orb_instance.get_next_passes.return_value = passes
        MockOrbital.return_value = orb_instance

        result = get_upcoming_passes()

        # Only passes with max_el >= 30 should remain (pass 1 and 3)
        assert len(result) == 2
        assert result[0].max_elevation_deg == 50.0
        assert result[1].max_elevation_deg == 65.0
