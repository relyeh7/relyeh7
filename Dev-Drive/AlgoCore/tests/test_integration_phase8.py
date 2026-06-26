import json
from unittest.mock import patch, MagicMock


def test_position_manager_run_does_not_replay_fills():
    """Ensure PositionManager.run() uses subscribe_since — cursor advances, no fill replay."""
    import services.positions.manager as mod

    calls = []

    def fake_subscribe_since(channel, last_id):
        calls.append((channel, last_id))
        # Second call should use the stream ID returned from first, not "0" again
        if len(calls) == 1:
            return [{"symbol": "BTCUSDT", "side": "buy", "price": "50000", "size": "0.01", "strategy": "ml"}], "111-0"
        raise SystemExit

    with patch.object(mod, "subscribe_since", side_effect=fake_subscribe_since), \
         patch.object(mod, "set_state"), \
         patch.object(mod, "publish"), \
         patch.object(mod, "get_state", return_value=None), \
         patch("time.sleep"):
        from services.positions.manager import PositionManager
        pm = PositionManager(journal=MagicMock())
        try:
            pm.run()
        except SystemExit:
            pass

    assert len(calls) >= 2, "run() must loop at least twice"
    # Second call must use the returned stream ID "111-0", not "0"
    assert calls[1][1] == "111-0", (
        f"Second call must use returned stream ID '111-0', got '{calls[1][1]}'"
    )


def test_execution_bridge_cursor_advances():
    """Ensure ExecutionBridge cursor advances with real stream ID after decisions."""
    import services.execution_bridge.bridge as mod

    calls = []

    def fake_subscribe_since(channel, last_id):
        calls.append((channel, last_id))
        if len(calls) == 1:
            return [{"action": "BUY", "confidence": 0.9, "strategy": "ml"}], "999-0"
        raise SystemExit

    with patch.object(mod, "subscribe_since", side_effect=fake_subscribe_since), \
         patch.object(mod, "publish"), \
         patch("time.sleep"):
        from services.execution_bridge.bridge import ExecutionBridge
        bridge = ExecutionBridge("BTCUSDT", "bitget")
        try:
            bridge.run()
        except SystemExit:
            pass

    assert calls[1][1] == "999-0", (
        f"Second call must use stream ID '999-0', got '{calls[1][1]}'"
    )


def test_build_context_returns_updated_cursor():
    """Ensure build_context returns 4-tuple with updated last_signal_id from subscribe_since."""
    import services.orchestrator.context as mod

    with patch.object(mod, "get_state", return_value=None), \
         patch.object(mod, "subscribe_since", return_value=([], "500-0")):
        from services.orchestrator.context import build_context
        _, _, _, last_id = build_context("0")

    assert last_id == "500-0"


def test_docker_compose_prod_has_all_services():
    """Ensure docker-compose.prod.yml has all 11 expected services."""
    import yaml, pathlib

    path = pathlib.Path("H:/Dev-Drive/AlgoCore/docker-compose.prod.yml")
    assert path.exists(), "docker-compose.prod.yml must exist"
    data = yaml.safe_load(path.read_text())
    services = set(data["services"].keys())
    required = {
        "redis", "data", "risk", "sltp", "executor", "performance",
        "dashboard", "positions", "orchestrator", "notifications", "execution_bridge"
    }
    missing = required - services
    assert not missing, f"docker-compose.prod.yml is missing services: {missing}"
