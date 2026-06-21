import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_requests():
    with patch("services.executor.crypto.binance_client.requests") as m:
        yield m


def _mock_response(mock_requests, json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    mock_requests.get.return_value = resp
    mock_requests.post.return_value = resp
    return resp


def test_get_ticker(mock_requests):
    from services.executor.crypto.binance_client import BinanceClient
    _mock_response(mock_requests, {"price": "65000.50"})
    assert BinanceClient().get_ticker("BTCUSDT") == 65000.50


def test_get_balance(mock_requests):
    from services.executor.crypto.binance_client import BinanceClient
    _mock_response(mock_requests, [
        {"asset": "BTC",  "free": "0.001"},
        {"asset": "USDT", "free": "300.0"},
    ])
    assert BinanceClient().get_balance("USDT") == 300.0


def test_place_order(mock_requests):
    from services.executor.crypto.binance_client import BinanceClient
    _mock_response(mock_requests, {"orderId": 12345678})
    oid = BinanceClient().place_order("BTCUSDT", "buy", 64900.0, 0.001)
    assert oid == "12345678"
