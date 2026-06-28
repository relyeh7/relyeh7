from unittest.mock import patch
import shared.state as state_mod
import services.dashboard.api.main as main_mod
import services.dashboard.api.routes.metrics as metrics_mod


def test_redis_alive_false_when_ping_raises():
    """redis_alive() returns False when ping fails — Phase 14."""
    from shared.state import redis_alive

    with patch.object(state_mod, "_redis") as mock_redis:
        mock_redis.ping.side_effect = Exception("connection refused")
        assert redis_alive() is False


def test_status_services_risk_down_when_no_state():
    """GET /status services.risk must be 'down' when risk:state is absent — Phase 14."""
    from fastapi.testclient import TestClient

    with patch("services.dashboard.api.routes.status.get_state", return_value=None):
        client = TestClient(main_mod.app)
        resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["services"]["risk"] == "down"


def test_metrics_prometheus_type_headers_present():
    """GET /metrics must include # TYPE headers for all metrics — Phase 14."""
    from fastapi.testclient import TestClient

    with patch.object(metrics_mod, "get_state", return_value=None):
        client = TestClient(main_mod.app)
        resp = client.get("/metrics")

    text = resp.text
    assert "# TYPE algocore_drawdown_pct gauge" in text
    assert "# TYPE algocore_ml_trades_total counter" in text
    assert "# HELP algocore_exposure_pct" in text
