from unittest.mock import patch
import services.dashboard.api.main as main_mod


def test_ws_live_sends_payload_with_required_keys():
    """ws_live must send JSON with risk, positions, ml_signal, sentiment keys."""
    from fastapi.testclient import TestClient

    state_map = {
        "risk:state": {"drawdown_pct": 1.5, "is_stopped": False},
        "positions":  {"BTCUSDT": {"qty": 0.5}},
        "ml_signal":  {},
        "sentiment":  {},
    }

    with patch.object(main_mod, "get_state", side_effect=state_map.get):
        client = TestClient(main_mod.app)
        with client.websocket_connect("/ws/live") as ws:
            data = ws.receive_json()

    assert "risk" in data, "ws_live payload must include 'risk'"
    assert "positions" in data, "ws_live payload must include 'positions'"
    assert "ml_signal" in data, "ws_live payload must include 'ml_signal'"
    assert "sentiment" in data, "ws_live payload must include 'sentiment'"
    assert data["risk"]["drawdown_pct"] == 1.5, (
        "risk data must reflect mocked get_state('risk:state')"
    )
    assert data["positions"]["BTCUSDT"]["qty"] == 0.5
