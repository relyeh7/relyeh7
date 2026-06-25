import importlib
from unittest.mock import MagicMock, patch

import services.executor.crypto.service as _svc_mod


def _decision(action: str = "BUY") -> dict:
    return {"action": action, "symbol": "BTCUSDT", "price": "50000",
            "size": "0.01", "strategy": "ml", "timestamp": "0-0"}


def test_executor_paper_mode_calls_paper_engine():
    importlib.reload(_svc_mod)
    mock_engine = MagicMock()
    mock_engine.run_once.return_value = {"symbol": "BTCUSDT", "side": "buy",
                                          "price": 50050.0, "size": 0.01}
    with patch.object(_svc_mod, "subscribe_since", return_value=([_decision("BUY")], "1-0")), \
         patch.object(_svc_mod, "settings") as mock_settings, \
         patch.object(_svc_mod, "publish"):
        mock_settings.paper_trading = True
        svc = _svc_mod.ExecutorService(paper_engine=mock_engine)
        svc._process_decisions()
    mock_engine.run_once.assert_called_once()


def test_executor_live_mode_places_real_order_and_tracks():
    importlib.reload(_svc_mod)
    mock_router  = MagicMock()
    mock_tracker = MagicMock()
    mock_router.place_order.return_value = "ord-123"

    with patch.object(_svc_mod, "subscribe_since", return_value=([_decision("BUY")], "1-0")), \
         patch.object(_svc_mod, "settings") as mock_settings, \
         patch.object(_svc_mod, "publish"):
        mock_settings.paper_trading = False
        svc = _svc_mod.ExecutorService(router=mock_router, tracker=mock_tracker)
        svc._process_decisions()
    mock_router.place_order.assert_called_once()
    mock_tracker.track.assert_called_once()


def test_executor_publishes_order_rejected_on_exception():
    importlib.reload(_svc_mod)
    mock_router = MagicMock()
    mock_router.place_order.side_effect = Exception("exchange down")

    with patch.object(_svc_mod, "subscribe_since", return_value=([_decision("BUY")], "1-0")), \
         patch.object(_svc_mod, "settings") as mock_settings, \
         patch.object(_svc_mod, "publish") as mock_pub:
        mock_settings.paper_trading = False
        svc = _svc_mod.ExecutorService(router=mock_router)
        svc._process_decisions()
    channels = [call[0][0] for call in mock_pub.call_args_list]
    assert "order:rejected" in channels
