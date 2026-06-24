from unittest.mock import MagicMock, patch
from shared import events


def test_rest_poller_poll_once_writes_price_state():
    mock_router = MagicMock()
    mock_router.get_ticker.side_effect = lambda symbol: 50000.0 if symbol == "BTCUSDT" else 3000.0

    with patch("services.data.feeds.rest_poller.set_state") as mock_set, \
         patch("services.data.feeds.rest_poller.publish"):
        from services.data.feeds.rest_poller import RestPriceFeed
        feed = RestPriceFeed(router=mock_router, symbols=["BTCUSDT", "ETHUSDT"], poll_sec=30)
        ticks = feed.poll_once()

    assert len(ticks) == 2
    symbols = {t["symbol"] for t in ticks}
    assert symbols == {"BTCUSDT", "ETHUSDT"}
    assert mock_set.call_count == 2
    calls = [c[0] for c in mock_set.call_args_list]
    keys = [c[0] for c in calls]
    assert "price:BTCUSDT" in keys
    assert "price:ETHUSDT" in keys


def test_rest_poller_poll_once_skips_failed_symbol():
    mock_router = MagicMock()
    mock_router.get_ticker.side_effect = [50000.0, Exception("network error")]

    with patch("services.data.feeds.rest_poller.set_state") as mock_set, \
         patch("services.data.feeds.rest_poller.publish"):
        from services.data.feeds.rest_poller import RestPriceFeed
        feed = RestPriceFeed(router=mock_router, symbols=["BTCUSDT", "ETHUSDT"], poll_sec=30)
        ticks = feed.poll_once()

    assert len(ticks) == 1
    assert ticks[0]["symbol"] == "BTCUSDT"
    assert mock_set.call_count == 1


def test_rest_poller_publishes_price_tick_event():
    mock_router = MagicMock()
    mock_router.get_ticker.return_value = 60000.0

    with patch("services.data.feeds.rest_poller.set_state"), \
         patch("services.data.feeds.rest_poller.publish") as mock_pub:
        from services.data.feeds.rest_poller import RestPriceFeed
        feed = RestPriceFeed(router=mock_router, symbols=["BTCUSDT"], poll_sec=30)
        feed.poll_once()

    mock_pub.assert_called_once()
    channel, payload = mock_pub.call_args[0]
    assert channel == events.PRICE_TICK
    assert payload["symbol"] == "BTCUSDT"
    assert payload["price"] == 60000.0
