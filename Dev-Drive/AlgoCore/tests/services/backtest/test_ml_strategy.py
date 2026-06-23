import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta


def _make_ohlcv(n: int = 120) -> pd.DataFrame:
    np.random.seed(99)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = 3000.0
    rows = []
    for i in range(n):
        price = price * (1 + np.random.uniform(-0.005, 0.005))
        rows.append({
            "timestamp": (base + timedelta(minutes=15 * i)).isoformat(),
            "open": price * 0.999, "high": price * 1.002,
            "low": price * 0.998, "close": price,
            "volume": float(np.random.randint(500, 2000)),
        })
    return pd.DataFrame(rows)


def test_ml_strategy_backtest_returns_result():
    from services.backtest.ml_strategy import MLStrategyBacktester
    df = _make_ohlcv(120)
    bt = MLStrategyBacktester("BTCUSDT")
    result = bt.run(df)
    assert result.symbol == "BTCUSDT"
    assert result.strategy == "xgboost"
    assert 0.0 <= result.win_rate <= 1.0
    assert len(result.equity_curve) > 0


def test_ml_strategy_backtest_uses_oos_split():
    from services.backtest.ml_strategy import MLStrategyBacktester
    df = _make_ohlcv(120)
    bt = MLStrategyBacktester("BTCUSDT")
    result = bt.run(df)
    # equity curve length should correspond to OOS portion (~20% of feature rows)
    assert len(result.equity_curve) < 120
