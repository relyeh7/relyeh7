import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta


def _make_ohlcv(n: int = 60) -> pd.DataFrame:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    np.random.seed(0)
    rows = []
    price = 3000.0
    for i in range(n):
        price = price * (1 + np.random.uniform(-0.002, 0.002))
        rows.append({
            "timestamp": (base + timedelta(minutes=15 * i)).isoformat(),
            "open":   price * 0.999,
            "high":   price * 1.002,
            "low":    price * 0.998,
            "close":  price,
            "volume": float(np.random.randint(500, 2000)),
        })
    return pd.DataFrame(rows)


def test_build_features_returns_correct_columns():
    from services.ml.features import build_features
    df = _make_ohlcv(60)
    result = build_features(df)
    expected = {"rsi", "atr", "macd", "macd_signal", "macd_hist",
                "bb_width", "returns", "volume_ratio", "hour", "dow", "target"}
    assert set(result.columns) == expected


def test_build_features_drops_nan_rows():
    from services.ml.features import build_features
    df = _make_ohlcv(60)
    result = build_features(df)
    assert result.isnull().sum().sum() == 0
    assert len(result) < len(df)


def test_build_features_target_is_binary():
    from services.ml.features import build_features
    df = _make_ohlcv(60)
    result = build_features(df)
    assert set(result["target"].unique()).issubset({0, 1})


def test_build_features_time_columns():
    from services.ml.features import build_features
    df = _make_ohlcv(60)
    result = build_features(df)
    assert result["hour"].between(0, 23).all()
    assert result["dow"].between(0, 6).all()
