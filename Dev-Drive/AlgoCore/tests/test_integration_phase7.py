import json
from unittest.mock import patch, MagicMock


def test_subscribe_since_returns_correct_types():
    from shared.state import subscribe_since
    with patch("shared.state._redis") as mock_redis:
        mock_redis.xread.return_value = []
        payloads, last_id = subscribe_since("test:channel")
    assert isinstance(payloads, list)
    assert isinstance(last_id, str)


def test_subscribe_since_real_stream_id_returned():
    import json
    from shared.state import subscribe_since
    fake_id = "1718000000000-0"
    fake_data = {"price": 50000.0, "symbol": "BTCUSDT"}
    fake_xread = [("test:ch", [(fake_id, {"payload": json.dumps(fake_data)})])]
    with patch("shared.state._redis") as mock_redis:
        mock_redis.xread.return_value = fake_xread
        payloads, last_id = subscribe_since("test:ch", "0")
    assert last_id == fake_id
    assert payloads[0]["price"] == 50000.0


def test_performance_tracker_profit_factor():
    with patch("services.performance.tracker.set_state"), \
         patch("services.performance.tracker.publish"):
        from services.performance.tracker import PerformanceTracker
        tracker = PerformanceTracker()
        tracker.on_trade({"strategy": "ml", "pnl": 200.0})
        tracker.on_trade({"strategy": "ml", "pnl": -50.0})
        stats = tracker.get_stats("ml")
    assert "profit_factor" in stats
    assert stats["profit_factor"] == round(200.0 / 50.0, 4)  # 4.0


def test_risk_service_real_exposure_pct():
    positions = {
        "BTCUSDT": {"symbol": "BTCUSDT", "entry_price": 60000.0,
                    "size": 0.1, "strategy": "ml"}
    }

    def mock_get(key):
        if key.startswith("perf:"):
            return {"total_pnl": 0.0, "max_dd": 1.0}
        if key == "positions":
            return positions
        if key == "price:BTCUSDT":
            return {"price": 60000.0}
        return None

    with patch("services.risk.service.get_state", side_effect=mock_get), \
         patch("services.risk.service.settings") as mock_s:
        mock_s.stop_on_drawdown_pct = 6.0
        mock_s.initial_equity       = 10_000.0
        from services.risk.service import RiskService
        risk = RiskService().compute_risk()

    # 60000 * 0.1 = 6000 / 10000 * 100 = 60%
    assert abs(risk["exposure_pct"] - 60.0) < 0.01
    assert risk["open_positions"] == 1


def test_docker_compose_prod_is_valid_yaml():
    import yaml, pathlib
    path = pathlib.Path("H:/Dev-Drive/AlgoCore/docker-compose.prod.yml")
    assert path.exists(), "docker-compose.prod.yml must exist"
    data = yaml.safe_load(path.read_text())
    assert "services" in data
    assert "redis" in data["services"]
    assert "dashboard" in data["services"]
    assert "executor" in data["services"]
