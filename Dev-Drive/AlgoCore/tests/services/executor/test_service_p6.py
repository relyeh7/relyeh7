import importlib
from unittest.mock import MagicMock, patch

import services.executor.crypto.service as _svc_mod


def _decision(action: str = "BUY", strategy: str = "ml") -> dict:
    return {"action": action, "symbol": "BTCUSDT", "price": "50000",
            "size": "0.5", "strategy": strategy, "timestamp": "0-0"}


def test_executor_blocked_by_risk_gate():
    """When RiskGate.is_blocked() returns True, no orders are placed."""
    importlib.reload(_svc_mod)
    mock_engine = MagicMock()

    with patch.object(_svc_mod, "subscribe_since", return_value=([_decision("BUY")], "1-0")), \
         patch.object(_svc_mod, "settings") as mock_settings, \
         patch.object(_svc_mod, "publish"):
        mock_settings.paper_trading = True
        svc = _svc_mod.ExecutorService(paper_engine=mock_engine)
        svc._risk_gate = MagicMock()
        svc._risk_gate.is_blocked.return_value = True
        svc._process_decisions()

    mock_engine.run_once.assert_not_called()


def test_executor_not_blocked_when_risk_normal():
    """When RiskGate.is_blocked() returns False, paper orders proceed normally."""
    importlib.reload(_svc_mod)
    mock_engine = MagicMock()
    mock_engine.run_once.return_value = {"symbol": "BTCUSDT", "side": "buy",
                                          "price": 50050.0, "size": 0.01}

    with patch.object(_svc_mod, "subscribe_since", return_value=([_decision("BUY")], "1-0")), \
         patch.object(_svc_mod, "settings") as mock_settings, \
         patch.object(_svc_mod, "publish"):
        mock_settings.paper_trading = True
        svc = _svc_mod.ExecutorService(paper_engine=mock_engine)
        svc._risk_gate = MagicMock()
        svc._risk_gate.is_blocked.return_value = False
        svc._process_decisions()

    mock_engine.run_once.assert_called_once()


def test_executor_uses_subscribe_since():
    """Ensure _process_decisions uses subscribe_since for correct cursor tracking."""
    import services.executor.crypto.service as mod
    importlib.reload(mod)
    mock_engine = MagicMock()
    mock_engine.run_once.return_value = None

    with patch.object(mod, "subscribe_since", return_value=([], "0")) as mock_sub, \
         patch.object(mod, "settings") as mock_s, \
         patch.object(mod, "publish"):
        mock_s.paper_trading = True
        svc = mod.ExecutorService(paper_engine=mock_engine)
        svc._risk_gate = MagicMock()
        svc._risk_gate.is_blocked.return_value = False
        svc._process_decisions()
    mock_sub.assert_called_once()
