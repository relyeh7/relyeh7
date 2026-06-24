import importlib
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta


def _make_ohlcv(n: int = 120) -> pd.DataFrame:
    np.random.seed(77)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = 3000.0
    rows = []
    for i in range(n):
        price = price * (1 + np.random.uniform(-0.004, 0.004))
        rows.append({
            "timestamp": (base + timedelta(minutes=15 * i)).isoformat(),
            "open": price * 0.999, "high": price * 1.002,
            "low": price * 0.998, "close": price,
            "volume": float(np.random.randint(800, 2000)),
        })
    return pd.DataFrame(rows)


def test_all_phase4_modules_import():
    from shared.models import Trade, Position, BacktestResult
    from shared.events import TRADE_CLOSED, POSITION_UPDATE, PERF_UPDATE
    from services.journal.trade_journal import TradeJournal
    from services.positions.manager import PositionManager
    from services.backtest.engine import BacktestEngine
    from services.backtest.ml_strategy import MLStrategyBacktester
    from services.performance.tracker import PerformanceTracker
    assert True


def test_backtest_engine_end_to_end():
    from services.backtest.engine import BacktestEngine

    df = pd.DataFrame({
        "close": [100.0, 102.0, 101.0, 105.0, 103.0, 107.0, 106.0, 110.0, 109.0, 112.0],
        "open":  [99.0] * 10,
        "high":  [111.0] * 10,
        "low":   [98.0] * 10,
        "volume": [1000.0] * 10,
    })

    calls = [0]

    def signal_fn(row):
        calls[0] += 1
        if int(row.name) == 0: return "BUY"
        if int(row.name) == 5: return "SELL"
        return "HOLD"

    result = BacktestEngine("BTCUSDT", "test").run(df, signal_fn)
    assert result.n_trades >= 1
    assert result.total_pnl != 0.0


def test_position_manager_buy_then_sell():
    mock_journal = MagicMock()
    with patch("services.positions.manager.get_state", return_value=None), \
         patch("services.positions.manager.set_state"), \
         patch("services.positions.manager.publish"):
        import services.positions.manager as _pm_mod
        importlib.reload(_pm_mod)
        from services.positions.manager import PositionManager
        pm = PositionManager(mock_journal)
        pm.on_fill({"symbol": "BTCUSDT", "side": "buy", "price": "50000",
                    "size": "0.01", "strategy": "ml",
                    "timestamp": "2026-01-01T00:00:00Z"})
        trade = pm.on_fill({"symbol": "BTCUSDT", "side": "sell", "price": "51000",
                             "size": "0.01", "strategy": "ml",
                             "timestamp": "2026-01-01T01:00:00Z"})
    assert trade is not None
    assert trade.pnl > 0


def test_performance_tracker_accumulates_trades():
    with patch("services.performance.tracker.set_state"), \
         patch("services.performance.tracker.publish"):
        import services.performance.tracker as _pt_mod
        importlib.reload(_pt_mod)
        from services.performance.tracker import PerformanceTracker
        pt = PerformanceTracker()
        for pnl in [10.0, -5.0, 15.0, 8.0, -3.0]:
            pt.on_trade({"pnl": pnl, "strategy": "ml"})
        stats = pt.get_stats("ml")
    assert stats["n_trades"] == 5
    assert abs(stats["total_pnl"] - 25.0) < 0.01
    assert stats["win_rate"] == 0.6


def test_ml_strategy_backtest_produces_result():
    from services.backtest.ml_strategy import MLStrategyBacktester
    df = _make_ohlcv(120)
    bt = MLStrategyBacktester("ETHUSDT")
    result = bt.run(df)
    assert result.symbol == "ETHUSDT"
    assert result.strategy == "xgboost"
    assert isinstance(result.n_trades, int)
    assert 0.0 <= result.win_rate <= 1.0
