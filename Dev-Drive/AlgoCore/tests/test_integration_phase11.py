from unittest.mock import patch


def test_status_endpoint_returns_prices_from_symbol_state():
    """GET /status must build prices dict from price:{symbol} state, not stale 'prices' key."""
    from fastapi.testclient import TestClient

    captured_keys: list[str] = []

    def mock_get_state(key: str):
        captured_keys.append(key)
        if key == "risk:state":
            return {"drawdown_pct": 0.5, "is_stopped": False, "exposure_pct": 10.0}
        if key == "price:BTCUSDT":
            return {"price": "50000.0"}
        return None

    with patch("services.dashboard.api.routes.status.get_state", side_effect=mock_get_state), \
         patch("services.dashboard.api.routes.status.settings") as mock_s:
        mock_s.trading_symbols = ["BTCUSDT"]
        from services.dashboard.api.main import app
        client = TestClient(app)
        resp = client.get("/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["prices"] == {"BTCUSDT": 50000.0}, (
        f"/status prices must aggregate from price:{{symbol}} keys, got: {data['prices']}"
    )
    assert "price:BTCUSDT" in captured_keys, "status must call get_state('price:BTCUSDT')"
    assert "prices" not in captured_keys, "status must NOT call get_state('prices') — key never written"


def test_orchestrator_context_risk_dict_includes_daily_pnl_and_total_equity():
    """build_context() risk dict must include daily_pnl and total_equity — Phase 11."""
    import services.orchestrator.context as mod

    with patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "subscribe_since", return_value=([], "0")):
        from services.orchestrator.context import build_context
        _, risk, _, _ = build_context("0")

    assert "daily_pnl" in risk, "risk dict must include daily_pnl"
    assert "total_equity" in risk, "risk dict must include total_equity"
    assert isinstance(risk["daily_pnl"], float)
    assert isinstance(risk["total_equity"], float)


def test_orchestrator_prompt_shows_daily_pnl_absolute_and_equity():
    """LLM prompt must show daily_pnl in $ and total_equity — Phase 11."""
    import services.orchestrator.context as mod

    def mock_get_state(key: str):
        if key == "risk:state":
            return {
                "drawdown_pct": 0.5, "is_stopped": False, "exposure_pct": 15.0,
                "daily_pnl_pct": 2.5, "daily_pnl": 250.0, "total_equity": 10_250.0,
                "open_positions": 0,
            }
        return None

    with patch.object(mod, "get_state", side_effect=mock_get_state), \
         patch.object(mod, "subscribe_since", return_value=([], "0")):
        from services.orchestrator.context import build_context
        prompt, _, _, _ = build_context("0")

    assert "250.00" in prompt, "prompt must show daily_pnl absolute value"
    assert "10250.00" in prompt, "prompt must show total_equity"


def test_rules_daily_loss_threshold_triggers_stop_all():
    """apply_rules must return STOP_ALL when daily_pnl_pct <= -5.0 — Phase 11."""
    from services.orchestrator.rules import apply_rules

    risk_barely_over = {"drawdown_pct": 0.5, "is_stopped": False,
                        "exposure_pct": 10.0, "daily_pnl_pct": -5.0}
    risk_under       = {"drawdown_pct": 0.5, "is_stopped": False,
                        "exposure_pct": 10.0, "daily_pnl_pct": -4.99}

    assert apply_rules(risk_barely_over, [])["action"] == "STOP_ALL", (
        "daily_pnl_pct == -5.0 must trigger STOP_ALL"
    )
    assert apply_rules(risk_under, [])["action"] != "STOP_ALL", (
        "daily_pnl_pct == -4.99 must NOT trigger STOP_ALL"
    )
