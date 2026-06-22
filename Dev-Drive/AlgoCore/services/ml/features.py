import pandas as pd
import numpy as np


FEATURE_COLS = [
    "rsi", "atr", "macd", "macd_signal", "macd_hist",
    "bb_width", "returns", "volume_ratio", "hour", "dow",
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    out = pd.DataFrame(index=df.index)

    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    vol   = df["volume"]

    # RSI(14)
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, 1e-10)
    out["rsi"] = 100 - (100 / (1 + rs))

    # ATR(14)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    out["atr"] = tr.ewm(span=14, adjust=False).mean()

    # MACD(12, 26, 9)
    ema12              = close.ewm(span=12, adjust=False).mean()
    ema26              = close.ewm(span=26, adjust=False).mean()
    out["macd"]        = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"]   = out["macd"] - out["macd_signal"]

    # Bollinger Band width (20, 2σ)
    sma20          = close.rolling(20).mean()
    std20          = close.rolling(20).std()
    out["bb_width"] = ((sma20 + 2 * std20) - (sma20 - 2 * std20)) / sma20.replace(0, 1e-10)

    # Returns and volume ratio
    out["returns"]      = close.pct_change()
    out["volume_ratio"] = vol / vol.rolling(20).mean().replace(0, 1e-10)

    # Time features
    ts          = pd.to_datetime(df["timestamp"], utc=True)
    out["hour"] = ts.dt.hour.astype(float)
    out["dow"]  = ts.dt.dayofweek.astype(float)

    # Target: 1 if close 4 bars ahead > current close
    out["target"] = (close.shift(-4) > close).astype(int)

    # Drop NaN rows then last 4 (no future target)
    out = out.dropna()
    if len(out) > 4:
        out = out.iloc[:-4]
    return out.reset_index(drop=True)
