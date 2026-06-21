import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_requests():
    with patch("services.executor.crypto.bitget_client.requests") as m:
        yield m


def _mock_response(mock_requests, json_data: dict):
    resp = MagicMock()
    resp.json.return_value = {"code": "00000", "data": json_data}
    resp.raise_for_status = MagicMock()
    mock_requests.get.return_value = resp
    mock_requests.post.return_value = resp
    return resp


def test_get_ticker_returns_price(mock_requests):
    from services.executor.crypto.bitget_client import BitgetClient
    _mock_response(mock_requests, [{"lastPr": "2500.50"}])
    client = BitgetClient()
    price = client.get_ticker("ETHUSDT")
    assert price == 2500.50


def test_get_balance_returns_available(mock_requests):
    from services.executor.crypto.bitget_client import BitgetClient
    _mock_response(mock_requests, [
        {"coin": "USDT", "available": "500.25"},
        {"coin": "ETH",  "available": "0.1"},
    ])
    client = BitgetClient()
    balance = client.get_balance("USDT")
    assert balance == 500.25


def test_place_order_returns_order_id(mock_requests):
    from services.executor.crypto.bitget_client import BitgetClient
    _mock_response(mock_requests, {"orderId": "bg-order-999"})
    client = BitgetClient()
    order_id = client.place_order("ETHUSDT", "buy", 2490.0, 0.01)
    assert order_id == "bg-order-999"


def test_cancel_order_returns_true(mock_requests):
    from services.executor.crypto.bitget_client import BitgetClient
    _mock_response(mock_requests, {})
    client = BitgetClient()
    result = client.cancel_order("ETHUSDT", "bg-order-999")
    assert result is True
