from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def _get_client():
    with patch("services.dashboard.api.routes.positions.get_state", return_value={}), \
         patch("services.dashboard.api.routes.pnl.get_state", return_value={}), \
         patch("services.dashboard.api.routes.status.get_state", return_value={}), \
         patch("services.dashboard.api.routes.performance.get_state", return_value=None), \
         patch("services.dashboard.api.routes.trades.TradeJournal") as MockJournal:
        MockJournal.return_value.get_recent.return_value = []
        from services.dashboard.api.main import app
        return TestClient(app)


def test_positions_endpoint_returns_dict():
    client = _get_client()
    resp = client.get("/positions")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_trades_endpoint_returns_list():
    client = _get_client()
    resp = client.get("/trades")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_performance_endpoint_returns_stats():
    client = _get_client()
    resp = client.get("/performance/ml")
    assert resp.status_code == 200
    data = resp.json()
    assert "strategy" in data or "n_trades" in data or data == {}


def test_pnl_endpoint_returns_daily_pnl_pct():
    risk_state = {
        "total_equity": 10_500.0,
        "daily_pnl": 500.0,
        "daily_pnl_pct": 4.76,
        "drawdown_pct": 0.5,
    }
    with patch("services.dashboard.api.routes.pnl.get_state", return_value=risk_state):
        from services.dashboard.api.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/pnl")
    assert resp.status_code == 200
    data = resp.json()
    assert data["daily_pnl_pct"] == 4.76
    assert data["total_equity"] == 10_500.0
    assert data["daily_pnl"] == 500.0
