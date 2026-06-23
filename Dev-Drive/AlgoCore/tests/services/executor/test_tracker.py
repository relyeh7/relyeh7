from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


def _make_order(exchange: str = "bitget") -> "OrderState":
    from shared.models import OrderState, Side
    return OrderState(
        id="ord-abc", symbol="BTCUSDT", side=Side.BUY,
        price=50000.0, size=0.01, exchange=exchange, strategy="ml",
        placed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_tracker_track_stores_in_redis():
    mock_router = MagicMock()
    with patch("services.executor.crypto.tracker.set_state") as mock_set, \
         patch("services.executor.crypto.tracker.get_state", return_value={}):
        from services.executor.crypto.tracker import OrderTracker
        ot = OrderTracker(mock_router)
        ot.track(_make_order())
    mock_set.assert_called_once()
    key, val = mock_set.call_args[0]
    assert key == "pending_orders"
    assert "ord-abc" in val


def test_tracker_poll_fills_publishes_on_fill():
    mock_router = MagicMock()
    mock_router.get_order_status.return_value = "filled"
    mock_router.get_ticker.return_value = 51000.0

    stored = {"ord-abc": _make_order().model_dump(mode="json")}
    with patch("services.executor.crypto.tracker.get_state", return_value=stored), \
         patch("services.executor.crypto.tracker.set_state"), \
         patch("services.executor.crypto.tracker.publish") as mock_pub:
        from services.executor.crypto.tracker import OrderTracker
        ot = OrderTracker(mock_router)
        fills = ot.poll_fills()
    assert len(fills) == 1
    mock_pub.assert_called_once()
    channel, payload = mock_pub.call_args[0]
    assert channel == "order:filled"


def test_tracker_poll_fills_skips_pending_orders():
    mock_router = MagicMock()
    mock_router.get_order_status.return_value = "pending"

    stored = {"ord-abc": _make_order().model_dump(mode="json")}
    with patch("services.executor.crypto.tracker.get_state", return_value=stored), \
         patch("services.executor.crypto.tracker.set_state"), \
         patch("services.executor.crypto.tracker.publish") as mock_pub:
        from services.executor.crypto.tracker import OrderTracker
        ot = OrderTracker(mock_router)
        fills = ot.poll_fills()
    assert fills == []
    mock_pub.assert_not_called()
