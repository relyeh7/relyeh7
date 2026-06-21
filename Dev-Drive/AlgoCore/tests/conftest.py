import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_redis():
    with patch("shared.state._redis") as mock:
        mock.xadd = MagicMock()
        mock.xread = MagicMock(return_value=[])
        mock.set = MagicMock()
        mock.get = MagicMock(return_value=None)
        yield mock


@pytest.fixture
def mock_bitget_client():
    client = MagicMock()
    client.get_ticker.return_value = 2500.00
    client.place_order.return_value = "test-order-123"
    client.get_balance.return_value = 500.0
    return client


@pytest.fixture
def mock_binance_client():
    client = MagicMock()
    client.get_ticker.return_value = 65000.00
    client.place_order.return_value = "987654321"
    client.get_balance.return_value = 500.0
    return client
