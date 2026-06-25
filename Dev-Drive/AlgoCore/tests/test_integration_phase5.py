from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


def test_all_phase5_modules_import():
    from shared.models import OrderState
    from shared.events import ORDER_REJECTED
    from shared.config import settings
    from services.paper.engine import PaperEngine
    from services.executor.crypto.tracker import OrderTracker
    from services.routing.symbol_router import SymbolRouter
    assert settings.paper_trading is True
    assert hasattr(settings, "trading_symbols")
    assert hasattr(settings, "api_key")
    assert ORDER_REJECTED == "order:rejected"


def test_paper_engine_fill_loop():
    with patch("services.paper.engine.publish"), \
         patch("services.paper.engine.get_state", return_value={"price": 60000.0}):
        from services.paper.engine import PaperEngine
        engine = PaperEngine(slippage_pct=0.0)
        decision = {"symbol": "BTCUSDT", "action": "BUY", "size": "0.1", "strategy": "test"}
        fill = engine.run_once(decision)
    assert fill is not None
    assert fill["price"] == 60000.0
    assert fill["size"] == 0.1


def test_order_tracker_stores_and_polls():
    from shared.models import OrderState, Side
    mock_router = MagicMock()
    mock_router.get_order_status.return_value = "pending"

    with patch("services.executor.crypto.tracker.get_state", return_value={}), \
         patch("services.executor.crypto.tracker.set_state") as mock_set, \
         patch("services.executor.crypto.tracker.publish"):
        from services.executor.crypto.tracker import OrderTracker
        ot = OrderTracker(mock_router)
        order = OrderState(
            id="ord-999", symbol="ETHUSDT", side=Side.BUY,
            price=3000.0, size=0.5, exchange="bitget", strategy="rl",
            placed_at=datetime.now(timezone.utc),
        )
        ot.track(order)

    assert mock_set.called
    call_key, call_val = mock_set.call_args[0]
    assert call_key == "pending_orders"
    assert "ord-999" in call_val


def test_symbol_router_deduplication_and_symbols():
    from services.routing.symbol_router import SymbolRouter
    router = SymbolRouter(["BTCUSDT", "ETHUSDT", "BTCUSDT"])
    symbols = router.get_symbols()
    assert len(symbols) == 2
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols


def test_alert_subscriber_trade_closed():
    mock_tg = MagicMock()
    with patch("services.notifications.alerts.get_state", return_value=None):
        from services.notifications.alerts import AlertSubscriber
        sub = AlertSubscriber(client=mock_tg)
        sub.on_trade_closed({
            "symbol": "SOLUSDT", "side": "buy",
            "pnl": 42.5, "strategy": "rl",
            "closed_at": "2026-01-01T00:00:00Z",
        })
    mock_tg.send.assert_called_once()
    msg = mock_tg.send.call_args[0][0]
    assert "SOLUSDT" in msg
    assert "42.5" in msg or "+42.5" in msg


def test_metrics_endpoint_content():
    with patch("services.dashboard.api.routes.metrics.get_state", return_value=None):
        from services.dashboard.api.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "algocore_drawdown_pct" in body
    assert "algocore_ml_trades_total" in body
    assert "algocore_rl_total_pnl" in body
