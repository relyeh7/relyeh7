"""Phase 19 smoke tests — Graceful SIGTERM Shutdown."""
import signal
from unittest.mock import MagicMock, patch


# ── RiskService ───────────────────────────────────────────────────────────────

def test_risk_service_registers_sigterm_on_run():
    """run() must register a SIGTERM handler before entering the loop."""
    import services.risk.service as mod

    with patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"), \
         patch.object(mod, "settings") as mock_settings, \
         patch("signal.signal") as mock_signal, \
         patch("time.sleep", side_effect=SystemExit):
        mock_settings.stop_on_drawdown_pct = 6.0
        mock_settings.daily_loss_limit_pct = 5.0
        mock_settings.initial_equity = 10_000.0
        mock_settings.trading_symbols = []
        from services.risk.service import RiskService
        svc = RiskService()
        try:
            svc.run()
        except SystemExit:
            pass

    registered_signals = [call[0][0] for call in mock_signal.call_args_list]
    assert signal.SIGTERM in registered_signals, "RiskService must register SIGTERM handler in run()"


def test_risk_service_sigterm_handler_flushes_baseline():
    """SIGTERM handler must call _save_baseline() before exiting."""
    import services.risk.service as mod

    with patch.object(mod, "get_state", return_value=None):
        from services.risk.service import RiskService
        svc = RiskService()

    svc._save_baseline = MagicMock()
    svc._register_shutdown()

    handler = signal.getsignal(signal.SIGTERM)
    try:
        handler(signal.SIGTERM, None)
    except SystemExit:
        pass

    svc._save_baseline.assert_called_once()


# ── PerformanceTracker ────────────────────────────────────────────────────────

def test_performance_tracker_registers_sigterm_on_run():
    """run() must register a SIGTERM handler before entering the event loop."""
    import services.performance.tracker as mod

    with patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"), \
         patch.object(mod, "subscribe_since", return_value=([], "0")), \
         patch("signal.signal") as mock_signal, \
         patch("time.sleep", side_effect=SystemExit):
        from services.performance.tracker import PerformanceTracker
        tracker = PerformanceTracker()
        try:
            tracker.run()
        except SystemExit:
            pass

    registered_signals = [call[0][0] for call in mock_signal.call_args_list]
    assert signal.SIGTERM in registered_signals, "PerformanceTracker must register SIGTERM handler in run()"


def test_performance_tracker_sigterm_handler_flushes_snapshot():
    """SIGTERM handler must call _save_snapshot() before exiting."""
    import services.performance.tracker as mod

    with patch.object(mod, "get_state", return_value=None):
        from services.performance.tracker import PerformanceTracker
        tracker = PerformanceTracker()

    tracker._save_snapshot = MagicMock()
    tracker._register_shutdown()

    handler = signal.getsignal(signal.SIGTERM)
    try:
        handler(signal.SIGTERM, None)
    except SystemExit:
        pass

    tracker._save_snapshot.assert_called_once()


# ── PositionManager ───────────────────────────────────────────────────────────

def test_position_manager_registers_sigterm_on_run():
    """run() must register a SIGTERM handler before entering the fill loop."""
    import services.positions.manager as mod

    mock_journal = MagicMock()
    mock_journal.get_open_positions.return_value = []

    with patch.object(mod, "get_state", return_value={}), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"), \
         patch.object(mod, "subscribe_since", return_value=([], "0")), \
         patch("signal.signal") as mock_signal, \
         patch("time.sleep", side_effect=SystemExit):
        from services.positions.manager import PositionManager
        mgr = PositionManager(mock_journal)
        try:
            mgr.run()
        except SystemExit:
            pass

    registered_signals = [call[0][0] for call in mock_signal.call_args_list]
    assert signal.SIGTERM in registered_signals, "PositionManager must register SIGTERM handler in run()"


def test_position_manager_sigterm_handler_flushes_to_redis():
    """SIGTERM handler must call _save_to_redis() before exiting."""
    import services.positions.manager as mod

    mock_journal = MagicMock()
    mock_journal.get_open_positions.return_value = []

    with patch.object(mod, "get_state", return_value={}), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"):
        from services.positions.manager import PositionManager
        mgr = PositionManager(mock_journal)

    mgr._save_to_redis = MagicMock()
    mgr._register_shutdown()

    handler = signal.getsignal(signal.SIGTERM)
    try:
        handler(signal.SIGTERM, None)
    except SystemExit:
        pass

    mgr._save_to_redis.assert_called_once()
