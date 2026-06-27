from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import shared.config as config_mod


def _client_with_routes_mocked():
    with patch("services.dashboard.api.routes.positions.get_state", return_value={}), \
         patch("services.dashboard.api.routes.pnl.get_state", return_value={}), \
         patch("services.dashboard.api.routes.status.get_state", return_value={}), \
         patch("services.dashboard.api.routes.performance.get_state", return_value=None), \
         patch("services.dashboard.api.routes.metrics.get_state", return_value=None), \
         patch("services.dashboard.api.routes.trades.TradeJournal") as MockJournal:
        MockJournal.return_value.get_recent.return_value = []
        from services.dashboard.api.main import app
        return TestClient(app, raise_server_exceptions=False)


def test_metrics_endpoint_returns_prometheus_format():
    with patch("services.dashboard.api.routes.metrics.get_state", return_value=None):
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "algocore_drawdown_pct" in resp.text
    assert "algocore_ml_trades_total" in resp.text


def test_auth_blocks_without_api_key_header():
    client = _client_with_routes_mocked()
    original = config_mod.settings.api_key
    try:
        config_mod.settings.api_key = "mysecret"
        resp = client.get("/positions")
    finally:
        config_mod.settings.api_key = original
    assert resp.status_code == 403


def test_auth_allows_health_without_key():
    client = _client_with_routes_mocked()
    original = config_mod.settings.api_key
    try:
        config_mod.settings.api_key = "mysecret"
        resp = client.get("/health")
    finally:
        config_mod.settings.api_key = original
    assert resp.status_code == 200


def test_auth_allows_metrics_without_key():
    with patch("services.dashboard.api.routes.metrics.get_state", return_value=None):
        from services.dashboard.api.main import app
        client = TestClient(app, raise_server_exceptions=False)
    original = config_mod.settings.api_key
    try:
        config_mod.settings.api_key = "mysecret"
        resp = client.get("/metrics")
    finally:
        config_mod.settings.api_key = original
    assert resp.status_code == 200


def test_auth_disabled_when_api_key_empty():
    client = _client_with_routes_mocked()
    original = config_mod.settings.api_key
    try:
        config_mod.settings.api_key = ""
        resp = client.get("/positions")
    finally:
        config_mod.settings.api_key = original
    assert resp.status_code == 200


def test_metrics_includes_daily_pnl_pct():
    risk_state = {"drawdown_pct": 1.5, "daily_pnl_pct": -2.3, "open_positions": 2}
    with patch("services.dashboard.api.routes.metrics.get_state", return_value=risk_state):
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "algocore_daily_pnl_pct" in resp.text
    assert "-2.3" in resp.text


def test_metrics_includes_exposure_pct_and_is_stopped():
    risk_state = {
        "drawdown_pct": 0.5, "daily_pnl_pct": 1.0, "open_positions": 1,
        "exposure_pct": 35.0, "is_stopped": True,
    }
    with patch("services.dashboard.api.routes.metrics.get_state", return_value=risk_state):
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "algocore_exposure_pct 35.0" in resp.text, (
        "metrics must include algocore_exposure_pct line"
    )
    assert "algocore_is_stopped 1" in resp.text, (
        "metrics must include algocore_is_stopped line; True → 1"
    )
