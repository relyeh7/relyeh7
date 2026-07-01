"""Phase 20 smoke tests — Health Check HTTP Servers."""
import signal
import urllib.request
from unittest.mock import MagicMock, patch


# ── shared/health.py ──────────────────────────────────────────────────────────

def test_health_server_returns_200():
    """start_health_server() must respond 200 on GET /health."""
    from shared.health import start_health_server
    server = start_health_server(19081)
    try:
        resp = urllib.request.urlopen("http://localhost:19081/health", timeout=3)
        assert resp.status == 200
        body = resp.read()
        assert b"ok" in body
    finally:
        server.shutdown()


def test_health_server_returns_404_for_unknown_path():
    """start_health_server() must respond 404 for any path other than /health."""
    from shared.health import start_health_server
    import urllib.error
    server = start_health_server(19082)
    try:
        try:
            urllib.request.urlopen("http://localhost:19082/unknown", timeout=3)
            assert False, "Expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()


def test_health_server_is_non_blocking():
    """start_health_server() must return immediately (daemon thread, non-blocking)."""
    import time
    from shared.health import start_health_server
    t0 = time.monotonic()
    server = start_health_server(19083)
    elapsed = time.monotonic() - t0
    server.shutdown()
    assert elapsed < 1.0, f"start_health_server blocked for {elapsed:.2f}s — must be non-blocking"


# ── RiskService starts health server ─────────────────────────────────────────

def test_risk_service_starts_health_server_on_run():
    """RiskService.run() must call start_health_server(8081)."""
    import services.risk.service as mod

    with patch("services.risk.service.start_health_server") as mock_hs, \
         patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"), \
         patch.object(mod, "settings") as mock_settings, \
         patch("signal.signal"), \
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

    mock_hs.assert_called_once_with(8081)


# ── PositionManager starts health server ─────────────────────────────────────

def test_position_manager_starts_health_server_on_run():
    """PositionManager.run() must call start_health_server(8082)."""
    import services.positions.manager as mod

    mock_journal = MagicMock()
    mock_journal.get_open_positions.return_value = []

    with patch("services.positions.manager.start_health_server") as mock_hs, \
         patch.object(mod, "get_state", return_value={}), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"), \
         patch.object(mod, "subscribe_since", return_value=([], "0")), \
         patch("signal.signal"), \
         patch("time.sleep", side_effect=SystemExit):
        from services.positions.manager import PositionManager
        mgr = PositionManager(mock_journal)
        try:
            mgr.run()
        except SystemExit:
            pass

    mock_hs.assert_called_once_with(8082)


# ── PerformanceTracker starts health server ───────────────────────────────────

def test_performance_tracker_starts_health_server_on_run():
    """PerformanceTracker.run() must call start_health_server(8083)."""
    import services.performance.tracker as mod

    with patch("services.performance.tracker.start_health_server") as mock_hs, \
         patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"), \
         patch.object(mod, "subscribe_since", return_value=([], "0")), \
         patch("signal.signal"), \
         patch("time.sleep", side_effect=SystemExit):
        from services.performance.tracker import PerformanceTracker
        tracker = PerformanceTracker()
        try:
            tracker.run()
        except SystemExit:
            pass

    mock_hs.assert_called_once_with(8083)
