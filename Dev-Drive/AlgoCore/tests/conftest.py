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
    client.get_ticker.return_value = {"lastPr": "2500.00", "vol": "1000.0"}
    client.place_order.return_value = {"orderId": "test-order-123"}
    client.get_account_balance.return_value = [
        {"coin": "USDT", "available": "500.0"},
        {"coin": "ETH", "available": "0.1"},
    ]
    return client


@pytest.fixture
def mock_binance_client():
    client = MagicMock()
    client.get_symbol_ticker.return_value = {"price": "65000.00"}
    client.order_limit_buy.return_value = {"orderId": 987654321}
    client.get_asset_balance.return_value = {"free": "500.0", "locked": "0.0"}
    return client
