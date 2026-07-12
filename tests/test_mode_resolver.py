from unittest.mock import patch
from core.mode_resolver import resolve_mode, OperatingMode, reset_mode_state

@patch('core.mode_resolver.is_internet_available', return_value=True)
@patch('core.mode_resolver._check_sdr_hardware', return_value=True)
def test_resolve_mode_dual(mock_sdr, mock_net):
    reset_mode_state()
    assert resolve_mode() == OperatingMode.DUAL

@patch('core.mode_resolver.is_internet_available', return_value=False)
@patch('core.mode_resolver._check_sdr_hardware', return_value=True)
def test_resolve_mode_sdr_offline(mock_sdr, mock_net):
    reset_mode_state()
    assert resolve_mode() == OperatingMode.SDR_OFFLINE

@patch('core.mode_resolver.is_internet_available', return_value=True)
@patch('core.mode_resolver._check_sdr_hardware', return_value=False)
def test_resolve_mode_api_only(mock_sdr, mock_net):
    reset_mode_state()
    assert resolve_mode() == OperatingMode.API_ONLY

@patch('core.mode_resolver.is_internet_available', return_value=False)
@patch('core.mode_resolver._check_sdr_hardware', return_value=False)
def test_resolve_mode_degraded(mock_sdr, mock_net):
    reset_mode_state()
    assert resolve_mode() == OperatingMode.DEGRADED
