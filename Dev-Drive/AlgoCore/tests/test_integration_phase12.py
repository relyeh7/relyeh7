from unittest.mock import patch


def test_rules_custom_stop_threshold_from_settings():
    """apply_rules must use settings.stop_on_drawdown_pct — Phase 12."""
    from services.orchestrator.rules import apply_rules

    with patch("services.orchestrator.rules.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 2.5
        mock_s.daily_loss_limit_pct = 5.0
        risk = {"drawdown_pct": 2.8, "is_stopped": False,
                "exposure_pct": 10.0, "daily_pnl_pct": 0.0}
        decision = apply_rules(risk, [])

    assert decision["action"] == "STOP_ALL", (
        "drawdown_pct=2.8 must trigger STOP_ALL when stop_on_drawdown_pct=2.5"
    )


def test_rules_custom_daily_loss_limit_from_settings():
    """apply_rules must use settings.daily_loss_limit_pct — Phase 12."""
    from services.orchestrator.rules import apply_rules

    with patch("services.orchestrator.rules.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        mock_s.daily_loss_limit_pct = 3.0
        risk = {"drawdown_pct": 1.0, "is_stopped": False,
                "exposure_pct": 10.0, "daily_pnl_pct": -3.5}
        decision = apply_rules(risk, [])

    assert decision["action"] == "STOP_ALL", (
        "daily_pnl_pct=-3.5 must trigger STOP_ALL when daily_loss_limit_pct=3.0"
    )


def test_status_price_state_without_price_key_excluded():
    """GET /status must exclude symbols whose state dict lacks 'price' key — Phase 12."""
    from fastapi.testclient import TestClient

    def mock_get_state(key: str):
        if key == "risk:state":
            return {"drawdown_pct": 0.0, "is_stopped": False, "exposure_pct": 0.0}
        if key == "price:ETHUSDT":
            return {"exchange": "binance"}  # no "price" key
        return None

    with patch("services.dashboard.api.routes.status.get_state", side_effect=mock_get_state), \
         patch("services.dashboard.api.routes.status.settings") as mock_s:
        mock_s.trading_symbols = ["ETHUSDT"]
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/status")

    assert resp.status_code == 200
    assert resp.json()["prices"] == {}, (
        "ETHUSDT must be excluded when its state has no 'price' key"
    )
