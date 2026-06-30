"""Phase 16 smoke tests — State Persistence & Compose Completeness."""
import yaml
from unittest.mock import patch


# ── T1/T2: Compose completeness ──────────────────────────────────────────────

def test_dev_compose_has_positions_sltp_performance():
    """docker-compose.yml must declare positions, sltp, and performance services."""
    with open("docker-compose.yml") as fh:
        data = yaml.safe_load(fh)
    services = set(data["services"].keys())
    for required in ("positions", "sltp", "performance"):
        assert required in services, f"Missing service in dev compose: {required}"


def test_prod_compose_has_postgres_ml_rl_sentiment():
    """docker-compose.prod.yml must declare postgres, ml, rl, and sentiment services."""
    with open("docker-compose.prod.yml") as fh:
        data = yaml.safe_load(fh)
    services = set(data["services"].keys())
    for required in ("postgres", "ml", "rl", "sentiment"):
        assert required in services, f"Missing service in prod compose: {required}"


def test_prod_compose_positions_depends_on_postgres():
    """positions service in prod must depend on postgres (needs TradeJournal)."""
    with open("docker-compose.prod.yml") as fh:
        data = yaml.safe_load(fh)
    deps = data["services"]["positions"].get("depends_on", {})
    assert "postgres" in deps, "positions must depend on postgres in prod compose"


# ── T3: RiskService daily baseline persistence ───────────────────────────────

def test_risk_service_loads_baseline_on_init():
    """RiskService must restore day_start_pnl and current_day from Redis on startup."""
    from services.risk.service import RiskService

    saved = {"day_start_pnl": 123.45, "current_day": 999999}
    with patch("services.risk.service.get_state", return_value=saved):
        svc = RiskService()

    assert svc._day_start_pnl == 123.45
    assert svc._current_day   == 999999


def test_risk_service_saves_baseline_on_day_rollover():
    """RiskService must persist the new baseline to Redis when the day changes."""
    from services.risk.service import RiskService

    with patch("services.risk.service.get_state", return_value=None):
        svc = RiskService()

    svc._current_day = 1  # simulate yesterday

    saved_calls = []
    with patch("services.risk.service.set_state", side_effect=lambda k, v: saved_calls.append((k, v))):
        svc._daily_pnl_pct(total_pnl=500.0, portfolio_equity=10_000.0)

    baseline_saves = [(k, v) for k, v in saved_calls if k == "risk:daily_baseline"]
    assert baseline_saves, "set_state('risk:daily_baseline', ...) must be called on day rollover"
    assert baseline_saves[0][1]["day_start_pnl"] == 500.0


# ── T4: PerformanceTracker snapshot persistence ───────────────────────────────

def test_performance_tracker_loads_snapshot_on_init():
    """PerformanceTracker must restore pnls/equity/max_dd from Redis on startup."""
    from services.performance.tracker import PerformanceTracker

    snap = {
        "ml": {"pnls": [10.0, -5.0], "equity": 10_005.0, "max_eq": 10_010.0, "max_dd": 0.05},
    }
    with patch("services.performance.tracker.get_state", return_value=snap):
        tracker = PerformanceTracker()

    assert tracker._pnls["ml"]   == [10.0, -5.0]
    assert tracker._equity["ml"] == 10_005.0
    assert tracker._max_dd["ml"] == 0.05


def test_performance_tracker_saves_snapshot_on_trade():
    """PerformanceTracker must call set_state('perf:snapshot', ...) after each trade."""
    from services.performance.tracker import PerformanceTracker

    with patch("services.performance.tracker.get_state", return_value=None):
        tracker = PerformanceTracker()

    saved_snapshots = []
    with patch("services.performance.tracker.set_state", side_effect=lambda k, v: saved_snapshots.append(k)), \
         patch("services.performance.tracker.publish"):
        tracker.on_trade({"strategy": "ml", "pnl": 50.0})

    assert "perf:snapshot" in saved_snapshots, "snapshot must be written after each trade"
