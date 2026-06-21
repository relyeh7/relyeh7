import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone


def test_bitget_feed_publishes_price_tick():
    with patch("shared.state.publish") as mock_publish:
        from services.data.feeds.bitget_feed import BitgetFeed

        feed = BitgetFeed(symbols=["ETHUSDT"])
        # Simular un mensaje WebSocket recibido
        raw_msg = {
            "action": "snapshot",
            "data": [{"instId": "ETHUSDT", "last": "2500.00", "vol24h": "10000"}],
        }
        feed._on_message(raw_msg)

        mock_publish.assert_called_once()
        channel, payload = mock_publish.call_args[0]
        assert channel == "price:tick"
        assert payload["symbol"] == "ETHUSDT"
        assert payload["price"] == 2500.0
        assert payload["exchange"] == "bitget"


def test_binance_feed_publishes_price_tick():
    with patch("shared.state.publish") as mock_publish:
        from services.data.feeds.binance_feed import BinanceFeed

        feed = BinanceFeed(symbols=["BTCUSDT"])
        raw_msg = {
            "s": "BTCUSDT",
            "c": "65000.00",
            "v": "500.0",
            "T": 1718900000000,
        }
        feed._on_message(raw_msg)

        mock_publish.assert_called_once()
        channel, payload = mock_publish.call_args[0]
        assert channel == "price:tick"
        assert payload["symbol"] == "BTCUSDT"
        assert payload["price"] == 65000.0
        assert payload["exchange"] == "binance"


def test_bitget_feed_ignores_malformed_message():
    with patch("shared.state.publish") as mock_publish:
        from services.data.feeds.bitget_feed import BitgetFeed

        feed = BitgetFeed(symbols=["ETHUSDT"])
        feed._on_message({"unexpected": "format"})
        mock_publish.assert_not_called()
