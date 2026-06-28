from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def _get_client():
    # Patches here exit when the function returns (before any request is made).
    # Only patch what is actually needed: TradeJournal prevents a real DB call.
    with patch("services.dashboard.api.routes.trades.TradeJournal") as MockJournal:
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


def test_status_endpoint_aggregates_symbol_prices():
    from fastapi.testclient import TestClient

    def mock_get_state(key):
        if key == "risk:state":
            return {"drawdown_pct": 1.5, "is_stopped": False, "exposure_pct": 20.0}
        if key == "price:BTCUSDT":
            return {"price": "45000.0"}
        return None

    with patch("services.dashboard.api.routes.status.get_state", side_effect=mock_get_state), \
         patch("services.dashboard.api.routes.status.settings") as mock_s:
        mock_s.trading_symbols = ["BTCUSDT"]
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/status")

    assert resp.status_code == 200
    data = resp.json()
    assert "BTCUSDT" in data["prices"], "prices must contain symbols from trading_symbols"
    assert data["prices"]["BTCUSDT"] == 45000.0
    assert data["risk"]["drawdown_pct"] == 1.5


def test_status_skips_symbol_when_price_key_missing():
    """Symbol with state present but no 'price' key must be silently excluded."""
    from fastapi.testclient import TestClient

    def mock_get_state(key):
        if key == "risk:state":
            return {"drawdown_pct": 0.5, "is_stopped": False, "exposure_pct": 10.0}
        if key == "price:BTCUSDT":
            return {"ts": 1234567890}  # present but missing "price" key
        return None

    with patch("services.dashboard.api.routes.status.get_state", side_effect=mock_get_state), \
         patch("services.dashboard.api.routes.status.settings") as mock_s:
        mock_s.trading_symbols = ["BTCUSDT"]
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/status")

    assert resp.status_code == 200
    data = resp.json()
    assert "BTCUSDT" not in data["prices"], (
        "Symbol whose state lacks 'price' key must be excluded from prices dict"
    )
    assert data["prices"] == {}


def test_status_via_shared_client_returns_expected_structure():
    """_get_client() helper must allow GET /status to return correct response structure."""
    client = _get_client()
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "services" in data
    assert "risk" in data
    assert "prices" in data
    assert isinstance(data["prices"], dict)


def test_status_services_risk_up_when_risk_state_present():
    from fastapi.testclient import TestClient

    def mock_get_state(key):
        if key == "risk:state":
            return {"drawdown_pct": 0.5, "is_stopped": False, "exposure_pct": 10.0}
        return None

    with patch("services.dashboard.api.routes.status.get_state", side_effect=mock_get_state):
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["services"]["risk"] == "up", "risk must be 'up' when risk:state is present"
    assert data["services"]["data"] == "down", "data must be 'down' when no symbol has price state"


def test_status_services_down_when_no_state():
    from fastapi.testclient import TestClient

    with patch("services.dashboard.api.routes.status.get_state", return_value=None):
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["services"]["risk"] == "down", "risk must be 'down' when risk:state is None"
    assert data["services"]["data"] == "down", "data must be 'down' when no price state"
