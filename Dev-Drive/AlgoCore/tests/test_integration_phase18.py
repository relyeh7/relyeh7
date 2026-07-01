"""Phase 18 smoke tests — Signal Routing Fix + Dashboard Trades."""
from unittest.mock import MagicMock, patch


_BUY_SIGNAL = {
    "symbol": "BTCUSDT", "action": "BUY", "confidence": 0.82,
    "strategy": "orchestrator", "exchange": "bitget",
    "timestamp": "2026-01-01T00:00:00Z",
}
_SELL_SIGNAL = {**_BUY_SIGNAL, "action": "SELL"}
_CANCEL_SIGNAL = {**_BUY_SIGNAL, "action": "CANCEL_ALL"}
_HOLD_SIGNAL = {**_BUY_SIGNAL, "action": "HOLD"}


# ── T1: ExecutorService reads SIGNAL_NEW ─────────────────────────────────────

def test_executor_subscribes_to_signal_new():
    """_process_decisions() must subscribe to events.SIGNAL_NEW, not ORCH_DECISION."""
    from services.executor.crypto import service as svc_mod
    from shared import events

    with patch.object(svc_mod, "subscribe_since", return_value=([], "0")) as mock_sub, \
         patch.object(svc_mod, "publish"), \
         patch("services.executor.crypto.service.RiskGate") as mock_gate_cls, \
         patch("services.executor.crypto.service.PaperEngine"), \
         patch("services.executor.crypto.service.ExchangeRouter"), \
         patch("services.executor.crypto.service.OrderTracker"):
        mock_gate_cls.return_value.is_blocked.return_value = False
        from services.executor.crypto.service import ExecutorService
        svc = ExecutorService()
        svc._process_decisions()

    mock_sub.assert_called_once()
    channel = mock_sub.call_args[0][0]
    assert channel == events.SIGNAL_NEW, (
        f"ExecutorService must subscribe to SIGNAL_NEW, got '{channel}'"
    )


def test_executor_paper_fill_on_buy_signal():
    """BUY signal from SIGNAL_NEW must trigger PaperEngine.run_once()."""
    from services.executor.crypto import service as svc_mod

    mock_paper = MagicMock()
    mock_paper.run_once.return_value = {
        "symbol": "BTCUSDT", "side": "buy", "price": 50000.0,
        "size": 0.01, "strategy": "orchestrator", "order_id": "x",
    }

    with patch.object(svc_mod, "subscribe_since", return_value=([_BUY_SIGNAL], "1")), \
         patch.object(svc_mod, "publish"), \
         patch.object(svc_mod, "settings") as mock_settings, \
         patch("services.executor.crypto.service.RiskGate") as mock_gate_cls, \
         patch("services.executor.crypto.service.ExchangeRouter"), \
         patch("services.executor.crypto.service.OrderTracker"):
        mock_settings.paper_trading = True
        mock_gate_cls.return_value.is_blocked.return_value = False
        from services.executor.crypto.service import ExecutorService
        svc = ExecutorService(paper_engine=mock_paper)
        svc._process_decisions()

    mock_paper.run_once.assert_called_once_with(_BUY_SIGNAL)


def test_executor_paper_fill_on_sell_signal():
    """SELL signal from SIGNAL_NEW must trigger PaperEngine.run_once()."""
    from services.executor.crypto import service as svc_mod

    mock_paper = MagicMock()
    mock_paper.run_once.return_value = None

    with patch.object(svc_mod, "subscribe_since", return_value=([_SELL_SIGNAL], "2")), \
         patch.object(svc_mod, "publish"), \
         patch.object(svc_mod, "settings") as mock_settings, \
         patch("services.executor.crypto.service.RiskGate") as mock_gate_cls, \
         patch("services.executor.crypto.service.ExchangeRouter"), \
         patch("services.executor.crypto.service.OrderTracker"):
        mock_settings.paper_trading = True
        mock_gate_cls.return_value.is_blocked.return_value = False
        from services.executor.crypto.service import ExecutorService
        svc = ExecutorService(paper_engine=mock_paper)
        svc._process_decisions()

    mock_paper.run_once.assert_called_once_with(_SELL_SIGNAL)


def test_executor_cancel_all_publishes_risk_alert():
    """CANCEL_ALL must publish RISK_ALERT and skip paper fill."""
    from services.executor.crypto import service as svc_mod
    from shared import events

    mock_paper = MagicMock()

    with patch.object(svc_mod, "subscribe_since", return_value=([_CANCEL_SIGNAL], "3")), \
         patch.object(svc_mod, "publish") as mock_pub, \
         patch.object(svc_mod, "settings") as mock_settings, \
         patch("services.executor.crypto.service.RiskGate") as mock_gate_cls, \
         patch("services.executor.crypto.service.ExchangeRouter"), \
         patch("services.executor.crypto.service.OrderTracker"):
        mock_settings.paper_trading = True
        mock_gate_cls.return_value.is_blocked.return_value = False
        from services.executor.crypto.service import ExecutorService
        svc = ExecutorService(paper_engine=mock_paper)
        svc._process_decisions()

    mock_paper.run_once.assert_not_called()
    mock_pub.assert_called_once()
    channel, payload = mock_pub.call_args[0]
    assert channel == events.RISK_ALERT
    assert payload["reason"] == "CANCEL_ALL"


def test_executor_ignores_hold_signal():
    """HOLD arriving at SIGNAL_NEW must be silently dropped — no fill, no alert."""
    from services.executor.crypto import service as svc_mod

    mock_paper = MagicMock()

    with patch.object(svc_mod, "subscribe_since", return_value=([_HOLD_SIGNAL], "4")), \
         patch.object(svc_mod, "publish") as mock_pub, \
         patch.object(svc_mod, "settings") as mock_settings, \
         patch("services.executor.crypto.service.RiskGate") as mock_gate_cls, \
         patch("services.executor.crypto.service.ExchangeRouter"), \
         patch("services.executor.crypto.service.OrderTracker"):
        mock_settings.paper_trading = True
        mock_gate_cls.return_value.is_blocked.return_value = False
        from services.executor.crypto.service import ExecutorService
        svc = ExecutorService(paper_engine=mock_paper)
        svc._process_decisions()

    mock_paper.run_once.assert_not_called()
    mock_pub.assert_not_called()


# ── T2: /trades endpoint (already implemented — smoke test) ──────────────────

def test_trades_endpoint_returns_list():
    """GET /trades must return a list (empty is OK when journal has no data)."""
    from fastapi.testclient import TestClient

    mock_journal_cls = MagicMock()
    mock_journal_cls.return_value.get_recent.return_value = []

    with patch("services.dashboard.api.routes.trades.TradeJournal", mock_journal_cls), \
         patch("services.dashboard.api.main.redis_alive", return_value=True):
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/trades")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_trades_endpoint_passes_limit_to_journal():
    """GET /trades?limit=5 must call journal.get_recent(limit=5)."""
    from fastapi.testclient import TestClient
    from shared.models import Trade, Side
    from datetime import datetime, timezone

    mock_trade = Trade(
        symbol="BTCUSDT", side=Side.BUY,
        entry_price=50000.0, exit_price=51000.0,
        size=0.01, pnl=9.9, strategy="ml",
        opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        closed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    mock_journal_cls = MagicMock()
    mock_journal_cls.return_value.get_recent.return_value = [mock_trade]

    with patch("services.dashboard.api.routes.trades.TradeJournal", mock_journal_cls), \
         patch("services.dashboard.api.main.redis_alive", return_value=True):
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/trades?limit=5")

    assert resp.status_code == 200
    mock_journal_cls.return_value.get_recent.assert_called_once_with(limit=5)
    data = resp.json()
    assert len(data) == 1
    assert data[0]["symbol"] == "BTCUSDT"
