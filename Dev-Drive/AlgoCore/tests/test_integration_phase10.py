from unittest.mock import patch


def test_risk_compute_risk_includes_total_equity_and_daily_pnl():
    """compute_risk() must include total_equity and daily_pnl — added in Phase 10."""
    import services.risk.service as mod

    with patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"):
        from services.risk.service import RiskService
        result = RiskService().compute_risk()

    assert "total_equity" in result, "compute_risk must include total_equity"
    assert "daily_pnl" in result, "compute_risk must include daily_pnl"
    assert isinstance(result["total_equity"], float)
    assert isinstance(result["daily_pnl"], float)


def test_dashboard_pnl_reads_risk_state_key():
    """GET /pnl must read from 'risk:state', not the stale 'risk' key."""
    from fastapi.testclient import TestClient

    risk_state = {"daily_pnl_pct": 3.14, "total_equity": 11_000.0,
                  "daily_pnl": 314.0, "drawdown_pct": 0.0}
    captured_keys: list[str] = []

    def mock_get_state(key: str):
        captured_keys.append(key)
        return risk_state if key == "risk:state" else None

    with patch("services.dashboard.api.routes.pnl.get_state", side_effect=mock_get_state):
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/pnl")

    assert resp.status_code == 200
    assert "risk:state" in captured_keys, (
        f"/pnl must read 'risk:state', called with: {captured_keys}"
    )
    assert resp.json()["daily_pnl_pct"] == 3.14


def test_metrics_includes_daily_pnl_pct_line():
    """GET /metrics must expose algocore_daily_pnl_pct — added in Phase 10."""
    from fastapi.testclient import TestClient

    with patch("services.dashboard.api.routes.metrics.get_state", return_value=None):
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/metrics")

    assert resp.status_code == 200
    assert "algocore_daily_pnl_pct" in resp.text, (
        "Metrics endpoint must expose algocore_daily_pnl_pct line"
    )


def test_risk_healthcheck_start_period_45s():
    """risk healthcheck start_period must be 45s — bumped from 30s in Phase 10."""
    import yaml
    import pathlib

    path = pathlib.Path(__file__).parents[1] / "docker-compose.prod.yml"
    data = yaml.safe_load(path.read_text())
    start_period = data["services"]["risk"]["healthcheck"]["start_period"]
    assert start_period == "45s", (
        f"risk healthcheck start_period must be '45s', got {start_period!r}"
    )
