from unittest.mock import patch
import services.dashboard.api.main as main_mod


def test_rules_drawdown_reason_uses_settings_value():
    """rules.py STOP_ALL reason must interpolate stop_on_drawdown_pct — Phase 13."""
    from services.orchestrator.rules import apply_rules

    with patch("services.orchestrator.rules.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 5.0
        mock_s.daily_loss_limit_pct = 5.0
        risk = {"drawdown_pct": 6.0, "is_stopped": False,
                "exposure_pct": 10.0, "daily_pnl_pct": 0.0}
        decision = apply_rules(risk, [])

    assert decision["action"] == "STOP_ALL"
    assert "5" in decision["reason"]
    assert "6" not in decision["reason"]


def test_metrics_exposure_pct_and_is_stopped_present():
    """GET /metrics must include algocore_exposure_pct and algocore_is_stopped — Phase 13."""
    from fastapi.testclient import TestClient

    risk_state = {
        "drawdown_pct": 1.0, "daily_pnl_pct": 0.5, "open_positions": 2,
        "exposure_pct": 60.0, "is_stopped": False,
    }
    with patch("services.dashboard.api.routes.metrics.get_state", return_value=risk_state):
        client = TestClient(main_mod.app)
        resp = client.get("/metrics")

    assert "algocore_exposure_pct 60.0" in resp.text
    assert "algocore_is_stopped 0" in resp.text


def test_ws_live_payload_has_four_required_keys():
    """ws_live must emit payload with risk, positions, ml_signal, sentiment — Phase 13."""
    from fastapi.testclient import TestClient

    state_map = {
        "risk:state": {"drawdown_pct": 0.0},
        "positions":  {},
        "ml_signal":  {},
        "sentiment":  {},
    }

    with patch.object(main_mod, "get_state", side_effect=state_map.get):
        client = TestClient(main_mod.app)
        with client.websocket_connect("/ws/live") as ws:
            data = ws.receive_json()

    for key in ("risk", "positions", "ml_signal", "sentiment"):
        assert key in data, f"ws_live payload must include '{key}'"
