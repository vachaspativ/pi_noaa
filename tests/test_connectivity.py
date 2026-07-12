from unittest.mock import patch
from core.connectivity import is_internet_available

@patch('socket.socket')
def test_internet_available(mock_socket):
    assert is_internet_available() == True

@patch('socket.socket')
def test_internet_unavailable(mock_socket):
    mock_socket.return_value.connect.side_effect = OSError
    assert is_internet_available() == False
