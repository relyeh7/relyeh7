import pandas as pd
import numpy as np


def _make_df(n: int = 100, trend: float = 0.001) -> pd.DataFrame:
    np.random.seed(42)
    price = 1000.0
    rows = []
    for i in range(n):
        price = price * (1 + trend + np.random.uniform(-0.002, 0.002))
        rows.append({"close": price, "open": price * 0.999,
                     "high": price * 1.001, "low": price * 0.999,
                     "volume": 1000.0})
    return pd.DataFrame(rows)


def _always_buy(row: pd.Series) -> str:
    return "BUY"


def _alternating(row: pd.Series) -> str:
    return "BUY" if int(row.name) % 20 == 0 else ("SELL" if int(row.name) % 20 == 10 else "HOLD")


def test_engine_returns_backtest_result():
    from services.backtest.engine import BacktestEngine
    df = _make_df(100)
    engine = BacktestEngine("BTCUSDT", "test")
    result = engine.run(df, _alternating)
    assert result.symbol == "BTCUSDT"
    assert result.strategy == "test"
    assert isinstance(result.n_trades, int)
    assert len(result.equity_curve) == len(df)


def test_engine_equity_curve_starts_at_initial():
    from services.backtest.engine import BacktestEngine
    df = _make_df(50)
    engine = BacktestEngine("BTCUSDT", "test", initial_equity=5000.0)
    result = engine.run(df, _alternating)
    assert result.equity_curve[0] == 5000.0


def test_engine_win_rate_between_zero_and_one():
    from services.backtest.engine import BacktestEngine
    df = _make_df(100)
    result = BacktestEngine("BTCUSDT", "test").run(df, _alternating)
    assert 0.0 <= result.win_rate <= 1.0


def test_engine_no_trades_returns_zero_metrics():
    from services.backtest.engine import BacktestEngine
    df = _make_df(20)
    result = BacktestEngine("BTCUSDT", "test").run(df, lambda row: "HOLD")
    assert result.n_trades == 0
    assert result.total_pnl == 0.0
    assert result.sharpe == 0.0
    assert result.win_rate == 0.0
