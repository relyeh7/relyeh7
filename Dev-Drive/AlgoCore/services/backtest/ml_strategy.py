import pandas as pd
from services.ml.features import build_features
from services.ml.models.xgboost_model import XGBoostModel
from services.ml.inference.predictor import Predictor
from services.backtest.engine import BacktestEngine
from shared.models import BacktestResult


def _surviving_positions(df: pd.DataFrame) -> list[int]:
    """Return the 0-based row positions of `df` that build_features retains.

    build_features does reset_index(drop=True) on entry, so all positions
    are 0-based.  We replicate the same dropna + iloc[:-4] logic to discover
    which indices survive, without importing the private internals.
    """
    close = df["close"].reset_index(drop=True)
    high  = df["high"].reset_index(drop=True)
    low   = df["low"].reset_index(drop=True)
    vol   = df["volume"].reset_index(drop=True)

    mask = pd.DataFrame(index=range(len(df)))

    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, 1e-10)
    mask["rsi"] = 100 - (100 / (1 + rs))

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    mask["atr"] = tr.ewm(span=14, adjust=False).mean()

    ema12             = close.ewm(span=12, adjust=False).mean()
    ema26             = close.ewm(span=26, adjust=False).mean()
    mask["macd"]      = ema12 - ema26
    mask["macd_signal"] = mask["macd"].ewm(span=9, adjust=False).mean()
    mask["macd_hist"]   = mask["macd"] - mask["macd_signal"]

    sma20            = close.rolling(20).mean()
    std20            = close.rolling(20).std()
    mask["bb_width"] = ((sma20 + 2*std20) - (sma20 - 2*std20)) / sma20.replace(0, 1e-10)
    mask["returns"]  = close.pct_change()
    mask["volume_ratio"] = vol / vol.rolling(20).mean().replace(0, 1e-10)

    ts              = pd.to_datetime(df["timestamp"].reset_index(drop=True), utc=True)
    mask["hour"]    = ts.dt.hour.astype(float)
    mask["dow"]     = ts.dt.dayofweek.astype(float)
    mask["target"]  = (close.shift(-4) > close).astype(int)

    mask = mask.dropna()
    if len(mask) > 4:
        mask = mask.iloc[:-4]
    return list(mask.index)


class MLStrategyBacktester:
    def __init__(self, symbol: str, model: XGBoostModel | None = None):
        self._symbol = symbol
        self._model  = model or XGBoostModel()

    def run(self, df: pd.DataFrame) -> BacktestResult:
        features = build_features(df)
        split    = int(len(features) * 0.8)
        train_df = features.iloc[:split]
        oos_df   = features.iloc[split:].reset_index(drop=True)

        self._model.fit(train_df)
        predictor = Predictor(self._model)
        X_oos = oos_df.drop(columns=["target"])

        # Recover the original close prices for the OOS rows so the engine
        # can compute PnL.  build_features resets the df index internally;
        # _surviving_positions reproduces the same row-keep logic.
        df_reset  = df.reset_index(drop=True)
        positions = _surviving_positions(df_reset)
        oos_positions = positions[split:]
        close_oos = df_reset["close"].iloc[oos_positions].reset_index(drop=True)

        # Build the DataFrame the engine iterates: feature columns + close
        oos_engine_df = oos_df.copy()
        oos_engine_df["close"] = close_oos.values

        def signal_fn(row: pd.Series) -> str:
            row_df = X_oos.iloc[[int(row.name)]]
            action, _ = predictor.predict_from_df(row_df)
            return action

        engine = BacktestEngine(self._symbol, "xgboost")
        return engine.run(oos_engine_df, signal_fn)
