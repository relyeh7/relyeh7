# AlgoCore Phase 2 — ML Service & Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live ML prediction layer (XGBoost baseline + LSTM ensemble), a LLM-driven orchestrator that synthesizes market state and ML signals into trading decisions every 15 minutes, and Telegram alert notifications.

**Architecture:** Three new services on top of Phase 1's Redis bus — `ml-service` fetches OHLCV candles via REST, builds features, trains XGBoost/LSTM, and publishes `Signal` objects to `ml:signal`; `orchestrator-service` reads risk state + ML signals from Redis every 15 min, calls Claude Haiku → Gemini Flash → deterministic fallback, and publishes `OrchestratorDecision` to `orchestrator:decision`; `notifications-service` subscribes to risk alerts + order fills + orchestrator decisions and sends Telegram messages.

**Tech Stack:** pandas>=2.0.0, numpy>=1.26.0, xgboost>=2.0.0, scikit-learn>=1.5.0, mlflow>=2.14.0, anthropic>=0.30.0, torch>=2.1.0 (Task 10 only), requests (already transitive dep)

## Global Constraints

- Python 3.11+: `X | Y` unions, `:=` walrus, f-strings
- Pydantic v2: `model_validate`, `model_dump` — never `parse_obj`, `.dict()`
- All secrets from `.env` — never hardcoded
- `set_state(key, data)` prepends `"state:"` internally — pass bare key `"ml"`, never `"state:ml"`
- `publish(channel, data)` wraps as `{"payload": json.dumps(data, default=str)}`
- `subscribe_once(channel)` returns `list[dict]` — each item is the deserialized inner payload
- `ML_SIGNAL = "ml:signal"` — published by ML service, consumed by orchestrator
- `ORCH_DECISION = "orchestrator:decision"` — already in events.py
- XGBoost target: `1` if `close.shift(-4) > close` else `0` (direction 4 M15 bars = 1 hour ahead)
- OOS split: last 20% of data; model promotes only if Sharpe ≥ 1.0 on OOS
- Sharpe formula: `mean(returns) / std(returns) * sqrt(252 * 96)` (96 bars/day × 252 days, M15)
- OHLCV DataFrame columns (exact): `timestamp` (ISO str), `open`, `high`, `low`, `close`, `volume`
- Feature columns (exact names, no others): `rsi`, `atr`, `macd`, `macd_signal`, `macd_hist`, `bb_width`, `returns`, `volume_ratio`, `hour`, `dow`
- Orchestrator LLM primary: `claude-haiku-4-5-20251001` via `anthropic.Anthropic`
- Orchestrator LLM fallback: `gemini-2.0-flash` via REST (same pattern as `BitgetBot/agents/orchestrator.py`)
- Telegram: plain `requests.post` to `https://api.telegram.org/bot{token}/sendMessage` — no library
- Patch location for tests: module-level (e.g., `patch("services.ml.data.fetcher.requests")`)
- All new packages added to `AlgoCore/requirements.txt`
- Branch for this work: `feat/algocore-phase2`

---

## File Map

```
AlgoCore/
├── requirements.txt                          MODIFY
├── shared/
│   ├── config.py                             MODIFY (+3 fields)
│   ├── models.py                             MODIFY (+OHLCVBar, +OrchestratorDecision)
│   └── events.py                             MODIFY (+ML_SIGNAL)
├── services/
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   └── fetcher.py        OHLCV REST from Bitget + Binance
│   │   ├── features.py           OHLCV DataFrame → feature DataFrame
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── xgboost_model.py  XGBClassifier wrapper
│   │   │   ├── lstm_model.py     PyTorch LSTM (Task 10)
│   │   │   └── ensemble.py       Weighted combiner (Task 10)
│   │   ├── training/
│   │   │   ├── __init__.py
│   │   │   └── pipeline.py       Train → Sharpe OOS → promote via MLflow
│   │   ├── inference/
│   │   │   ├── __init__.py
│   │   │   └── predictor.py      Load model + run inference → float confidence
│   │   ├── tracking/
│   │   │   ├── __init__.py
│   │   │   └── mlflow_tracker.py MLflow experiment + model registry wrapper
│   │   └── service.py            15-min loop: fetch→features→predict→publish Signal
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── context.py            Build market prompt from Redis state + ML signals
│   │   ├── tools.py              LLM tool schema for set_trading_action
│   │   ├── rules.py              Deterministic fallback rules (no API)
│   │   ├── agent.py              Claude→Gemini→rules chain
│   │   └── service.py            15-min orchestrator loop
│   └── notifications/
│       ├── __init__.py
│       ├── telegram.py           Bot API client
│       └── alerts.py             Redis subscriber → Telegram
└── tests/
    ├── services/
    │   ├── ml/
    │   │   ├── __init__.py
    │   │   ├── test_fetcher.py
    │   │   ├── test_features.py
    │   │   ├── test_xgboost_model.py
    │   │   ├── test_pipeline.py
    │   │   └── test_predictor.py
    │   ├── orchestrator/
    │   │   ├── __init__.py
    │   │   ├── test_rules.py
    │   │   └── test_agent.py
    │   └── notifications/
    │       ├── __init__.py
    │       └── test_telegram.py
    └── test_integration_ml.py
```

---

### Task 1: Shared Extensions — Models, Events, Config, Dependencies

**Files:**
- Modify: `AlgoCore/shared/config.py`
- Modify: `AlgoCore/shared/models.py`
- Modify: `AlgoCore/shared/events.py`
- Modify: `AlgoCore/requirements.txt`
- Test: `AlgoCore/tests/shared/test_models.py` (existing — append new tests)

**Interfaces:**
- Produces: `OHLCVBar(timestamp, open, high, low, close, volume)` — used by Tasks 2–7
- Produces: `OrchestratorDecision(action, market, exchange, strategy, capital_pct, reason, confidence, timestamp)` — used by Task 8
- Produces: `events.ML_SIGNAL = "ml:signal"` — used by Tasks 7, 8
- Produces: `settings.telegram_bot_token`, `settings.telegram_chat_id`, `settings.mlflow_tracking_uri` — used by Tasks 4–5, 9

- [ ] **Step 1: Append new tests for models**

```python
# AlgoCore/tests/shared/test_models.py  — append to end of file
def test_ohlcv_bar():
    from shared.models import OHLCVBar
    bar = OHLCVBar(timestamp="2026-01-01T00:00:00", open=100.0, high=105.0,
                   low=99.0, close=103.0, volume=1500.0)
    assert bar.close == 103.0
    d = bar.model_dump()
    assert d["volume"] == 1500.0

def test_orchestrator_decision_defaults():
    from shared.models import OrchestratorDecision
    dec = OrchestratorDecision(action="HOLD", reason="calm market", confidence=0.7)
    assert dec.market == "crypto"
    assert dec.capital_pct == 0.0
    assert dec.exchange == "auto"
```

- [ ] **Step 2: Run tests to see them fail**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/shared/test_models.py::test_ohlcv_bar AlgoCore/tests/shared/test_models.py::test_orchestrator_decision_defaults -v
```
Expected: `ImportError` or `FAILED`

- [ ] **Step 3: Add OHLCVBar and OrchestratorDecision to models.py**

```python
# AlgoCore/shared/models.py — full file replacement
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class Exchange(str, Enum):
    BITGET  = "bitget"
    BINANCE = "binance"
    MT5     = "mt5"


class Market(str, Enum):
    CRYPTO = "crypto"
    FOREX  = "forex"


class Side(str, Enum):
    BUY  = "buy"
    SELL = "sell"


class PriceTick(BaseModel):
    symbol:    str
    price:     float
    volume:    float
    timestamp: datetime
    exchange:  Exchange


class Signal(BaseModel):
    symbol:     str
    action:     str          # BUY | SELL | HOLD
    confidence: float = Field(ge=0.0, le=1.0)
    strategy:   str
    exchange:   Exchange
    timestamp:  datetime


class Order(BaseModel):
    order_id:  str
    symbol:    str
    side:      Side
    price:     float
    size:      float
    exchange:  Exchange
    status:    str           # open | filled | cancelled
    timestamp: datetime


class RiskState(BaseModel):
    total_equity:   float
    daily_pnl:      float = 0.0
    daily_pnl_pct:  float = 0.0
    drawdown_pct:   float = 0.0
    exposure_pct:   float = 0.0
    is_stopped:     bool  = False
    open_positions: int   = 0


class OHLCVBar(BaseModel):
    timestamp: str
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float


class OrchestratorDecision(BaseModel):
    action:      str                          # HOLD|BUY|SELL|ADJUST_POSITION|PAUSE_STRATEGY|RESUME_ALL|STOP_ALL
    market:      str  = "crypto"              # crypto|forex|both
    exchange:    str  = "auto"                # bitget|binance|mt5|auto
    strategy:    str  = "ml"                  # grid|rsi|ml|rl|technical
    capital_pct: float = Field(ge=0.0, le=1.0, default=0.0)
    reason:      str  = ""
    confidence:  float = Field(ge=0.0, le=1.0, default=0.5)
    timestamp:   str  = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
```

- [ ] **Step 4: Add ML_SIGNAL to events.py**

```python
# AlgoCore/shared/events.py — full file replacement
# Redis Stream channels
PRICE_TICK    = "price:tick"
SIGNAL_NEW    = "signal:new"
ML_SIGNAL     = "ml:signal"
ORDER_PLACED  = "order:placed"
ORDER_FILLED  = "order:filled"
RISK_UPDATE   = "risk:update"
RISK_ALERT    = "risk:alert"
ORCH_DECISION = "orchestrator:decision"
```

- [ ] **Step 5: Add Phase 2 config fields**

```python
# AlgoCore/shared/config.py — full file replacement
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Bitget
    bitget_api_key:        str = ""
    bitget_api_secret:     str = ""
    bitget_api_passphrase: str = ""

    # Binance
    binance_api_key:    str = ""
    binance_api_secret: str = ""

    # LLM
    anthropic_api_key: str = ""
    gemini_api_key:    str = ""

    # Infraestructura
    redis_url:    str = "redis://localhost:6379"
    postgres_url: str = "postgresql://algocore:algocore@localhost:5432/algocore"

    # Risk thresholds
    max_daily_drawdown_pct: float = 6.0
    stop_on_drawdown_pct:   float = 6.0
    max_exposure_pct:       float = 90.0

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id:   str = ""

    # MLflow
    mlflow_tracking_uri: str = "mlruns"


settings = Settings()
```

- [ ] **Step 6: Add Phase 2 dependencies to requirements.txt**

```
# AlgoCore/requirements.txt — append these lines
pandas==2.2.2
numpy==1.26.4
xgboost==2.1.1
scikit-learn==1.5.1
mlflow==2.14.3
anthropic==0.30.0
```

Note: `torch` is added in Task 10 only. `requests` is already a transitive dep.

- [ ] **Step 7: Run new tests to verify they pass**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/shared/test_models.py -v
```
Expected: all tests pass (original 5 + 2 new = 7)

- [ ] **Step 8: Commit**

```
git add AlgoCore/shared/ AlgoCore/requirements.txt AlgoCore/tests/shared/test_models.py
git commit -m "feat: add Phase 2 shared extensions (OHLCVBar, OrchestratorDecision, ML_SIGNAL)"
```

---

### Task 2: OHLCV Data Fetcher

**Files:**
- Create: `AlgoCore/services/ml/__init__.py`
- Create: `AlgoCore/services/ml/data/__init__.py`
- Create: `AlgoCore/services/ml/data/fetcher.py`
- Create: `AlgoCore/tests/services/ml/__init__.py`
- Create: `AlgoCore/tests/services/ml/test_fetcher.py`

**Interfaces:**
- Consumes: `requests` (HTTP), no Redis, no auth (public endpoints)
- Produces: `OHLCVFetcher.get_candles(symbol, exchange, interval, limit) -> pd.DataFrame`
  - returns DataFrame with columns exactly: `["timestamp", "open", "high", "low", "close", "volume"]`
  - `timestamp` column: ISO 8601 string (UTC)
  - all other columns: `float`
  - sorted ascending by timestamp, index reset (0, 1, 2, ...)

- [ ] **Step 1: Write the failing test**

```python
# AlgoCore/tests/services/ml/test_fetcher.py
from unittest.mock import patch, MagicMock


def _mock_bitget_response():
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "code": "00000",
        "data": [
            ["1711382400000", "3200.00", "3210.00", "3195.00", "3205.00", "1200.5", "0", "0", "0"],
            ["1711383300000", "3205.00", "3215.00", "3200.00", "3210.00", "1100.3", "0", "0", "0"],
        ]
    }
    return m


def _mock_binance_response():
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = [
        [1711382400000, "3200.00", "3210.00", "3195.00", "3205.00", "1200.5",
         1711383299999, "0", 100, "0", "0", "0"],
        [1711383300000, "3205.00", "3215.00", "3200.00", "3210.00", "1100.3",
         1711384199999, "0", 120, "0", "0", "0"],
    ]
    return m


def test_get_candles_bitget_returns_dataframe():
    with patch("services.ml.data.fetcher.requests.get", return_value=_mock_bitget_response()):
        from services.ml.data.fetcher import OHLCVFetcher
        df = OHLCVFetcher().get_candles("ETHUSDT", exchange="bitget", limit=2)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df["close"].iloc[0] == 3205.0
    assert isinstance(df["volume"].iloc[0], float)


def test_get_candles_binance_returns_dataframe():
    with patch("services.ml.data.fetcher.requests.get", return_value=_mock_binance_response()):
        from services.ml.data.fetcher import OHLCVFetcher
        df = OHLCVFetcher().get_candles("ETHUSDT", exchange="binance", limit=2)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df["open"].iloc[1] == 3205.0


def test_get_candles_unknown_exchange_raises():
    from services.ml.data.fetcher import OHLCVFetcher
    try:
        OHLCVFetcher().get_candles("ETHUSDT", exchange="unknown")
        assert False, "should raise"
    except ValueError:
        pass
```

- [ ] **Step 2: Run to verify failure**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_fetcher.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create empty `__init__.py` files**

```python
# AlgoCore/services/ml/__init__.py  (empty)
# AlgoCore/services/ml/data/__init__.py  (empty)
# AlgoCore/tests/services/ml/__init__.py  (empty)
```

- [ ] **Step 4: Implement OHLCVFetcher**

```python
# AlgoCore/services/ml/data/fetcher.py
import requests
import pandas as pd
from datetime import datetime, timezone


class OHLCVFetcher:
    _BITGET_BASE  = "https://api.bitget.com"
    _BINANCE_BASE = "https://api.binance.com"

    def get_candles(
        self,
        symbol: str,
        exchange: str = "bitget",
        interval: str = "15m",
        limit: int = 200,
    ) -> pd.DataFrame:
        if exchange == "bitget":
            return self._bitget(symbol, interval, limit)
        if exchange == "binance":
            return self._binance(symbol, interval, limit)
        raise ValueError(f"Unknown exchange: {exchange}")

    def _bitget(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        gran = interval.replace("m", "min").replace("h", "H")
        r = requests.get(
            f"{self._BITGET_BASE}/api/v2/spot/market/candles",
            params={"symbol": symbol, "granularity": gran, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        resp = r.json()
        if resp.get("code") != "00000":
            raise ValueError(f"Bitget error: {resp.get('msg')}")
        rows = []
        for raw in resp["data"]:
            ts_ms = int(raw[0])
            ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
            rows.append({
                "timestamp": ts_iso,
                "open":   float(raw[1]),
                "high":   float(raw[2]),
                "low":    float(raw[3]),
                "close":  float(raw[4]),
                "volume": float(raw[5]),
            })
        df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        return df

    def _binance(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        r = requests.get(
            f"{self._BINANCE_BASE}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        rows = []
        for raw in r.json():
            ts_ms = int(raw[0])
            ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
            rows.append({
                "timestamp": ts_iso,
                "open":   float(raw[1]),
                "high":   float(raw[2]),
                "low":    float(raw[3]),
                "close":  float(raw[4]),
                "volume": float(raw[5]),
            })
        df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
        return df
```

- [ ] **Step 5: Run tests to verify they pass**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_fetcher.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```
git add AlgoCore/services/ml/ AlgoCore/tests/services/ml/
git commit -m "feat: add OHLCV data fetcher for Bitget and Binance"
```

---

### Task 3: Feature Engineering

**Files:**
- Create: `AlgoCore/services/ml/features.py`
- Create: `AlgoCore/tests/services/ml/test_features.py`

**Interfaces:**
- Consumes: `pd.DataFrame` with columns `[timestamp, open, high, low, close, volume]`; min 30 rows (needs rolling windows up to 26)
- Produces: `build_features(df: pd.DataFrame) -> pd.DataFrame`
  - Returns new DataFrame with columns: `["rsi", "atr", "macd", "macd_signal", "macd_hist", "bb_width", "returns", "volume_ratio", "hour", "dow"]` — no OHLCV columns in output
  - Also returns `target` column: `int` (1 = close went up in 4 bars, 0 = down)
  - Rows with NaN dropped (first ~26 rows); last 4 rows dropped (no target)
  - Index reset

- [ ] **Step 1: Write the failing tests**

```python
# AlgoCore/tests/services/ml/test_features.py
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta


def _make_ohlcv(n: int = 60) -> pd.DataFrame:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
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
```

- [ ] **Step 2: Run to verify failure**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_features.py -v
```
Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement build_features**

```python
# AlgoCore/services/ml/features.py
import pandas as pd
import numpy as np


FEATURE_COLS = [
    "rsi", "atr", "macd", "macd_signal", "macd_hist",
    "bb_width", "returns", "volume_ratio", "hour", "dow",
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build ML features from an OHLCV DataFrame.

    Args:
        df: DataFrame with columns [timestamp, open, high, low, close, volume].
            Must have at least 30 rows.

    Returns:
        DataFrame with columns FEATURE_COLS + ["target"].
        NaN rows dropped, last 4 rows dropped (no future target), index reset.
    """
    df = df.copy().reset_index(drop=True)
    out = pd.DataFrame(index=df.index)

    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    vol   = df["volume"]

    # RSI(14)
    delta     = close.diff()
    gain      = delta.clip(lower=0)
    loss      = (-delta).clip(lower=0)
    avg_gain  = gain.ewm(com=13, adjust=False).mean()
    avg_loss  = loss.ewm(com=13, adjust=False).mean()
    rs        = avg_gain / avg_loss.replace(0, 1e-10)
    out["rsi"] = 100 - (100 / (1 + rs))

    # ATR(14)
    prev_close  = close.shift(1)
    tr          = pd.concat([
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
    sma20       = close.rolling(20).mean()
    std20       = close.rolling(20).std()
    out["bb_width"] = ((sma20 + 2 * std20) - (sma20 - 2 * std20)) / sma20.replace(0, 1e-10)

    # Returns and volume ratio
    out["returns"]      = close.pct_change()
    out["volume_ratio"] = vol / vol.rolling(20).mean().replace(0, 1e-10)

    # Time features
    ts             = pd.to_datetime(df["timestamp"], utc=True)
    out["hour"]    = ts.dt.hour.astype(float)
    out["dow"]     = ts.dt.dayofweek.astype(float)

    # Target: 1 if close 4 bars ahead > current close
    out["target"] = (close.shift(-4) > close).astype(int)

    # Drop NaN (from rolling windows) and last 4 rows (no target)
    out = out.dropna().iloc[:-4] if len(out) > 4 else out.dropna()
    return out.reset_index(drop=True)
```

- [ ] **Step 4: Run tests**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_features.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add AlgoCore/services/ml/features.py AlgoCore/tests/services/ml/test_features.py
git commit -m "feat: add ML feature engineering (RSI, ATR, MACD, BB, returns, time)"
```

---

### Task 4: MLflow Tracker

**Files:**
- Create: `AlgoCore/services/ml/tracking/__init__.py`
- Create: `AlgoCore/services/ml/tracking/mlflow_tracker.py`

**Interfaces:**
- Consumes: `mlflow` library, `settings.mlflow_tracking_uri`
- Produces:
  - `MLflowTracker(tracking_uri, experiment_name)`
  - `.start_run(run_name: str) -> str` — returns `run_id`
  - `.log_params(params: dict) -> None`
  - `.log_metrics(metrics: dict) -> None`
  - `.log_model(model, artifact_path: str) -> None` — logs sklearn-compatible model
  - `.register_model(run_id: str, artifact_path: str, name: str) -> None`
  - `.end_run() -> None`

- [ ] **Step 1: Write the failing tests**

```python
# AlgoCore/tests/services/ml/test_tracker.py   (new file)
from unittest.mock import patch, MagicMock, call


def test_mlflow_tracker_start_run_returns_run_id():
    with patch("services.ml.tracking.mlflow_tracker.mlflow") as mock_mlflow:
        mock_run = MagicMock()
        mock_run.info.run_id = "abc123"
        mock_mlflow.start_run.return_value.__enter__ = lambda s: mock_run
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.active_run.return_value = mock_run

        from services.ml.tracking.mlflow_tracker import MLflowTracker
        tracker = MLflowTracker("mlruns", "test-exp")
        run_id = tracker.start_run("test-run")
        assert isinstance(run_id, str)


def test_mlflow_tracker_log_metrics_calls_mlflow():
    with patch("services.ml.tracking.mlflow_tracker.mlflow") as mock_mlflow:
        mock_mlflow.set_tracking_uri = MagicMock()
        mock_mlflow.set_experiment = MagicMock()
        mock_mlflow.log_metrics = MagicMock()
        mock_mlflow.active_run.return_value = MagicMock(info=MagicMock(run_id="r1"))

        from services.ml.tracking.mlflow_tracker import MLflowTracker
        tracker = MLflowTracker("mlruns", "test-exp")
        tracker._run_id = "r1"
        tracker.log_metrics({"sharpe": 1.5, "accuracy": 0.62})
        mock_mlflow.log_metrics.assert_called_once_with({"sharpe": 1.5, "accuracy": 0.62})
```

- [ ] **Step 2: Run to verify failure**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_tracker.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement MLflowTracker**

```python
# AlgoCore/services/ml/tracking/__init__.py  (empty)

# AlgoCore/services/ml/tracking/mlflow_tracker.py
import mlflow
import mlflow.sklearn


class MLflowTracker:
    def __init__(self, tracking_uri: str = "mlruns", experiment_name: str = "algocore-ml"):
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment_name)
        self._run_id: str | None = None

    def start_run(self, run_name: str) -> str:
        run = mlflow.start_run(run_name=run_name)
        self._run_id = run.info.run_id
        return self._run_id

    def log_params(self, params: dict) -> None:
        mlflow.log_params(params)

    def log_metrics(self, metrics: dict) -> None:
        mlflow.log_metrics(metrics)

    def log_model(self, model, artifact_path: str) -> None:
        mlflow.sklearn.log_model(model, artifact_path)

    def register_model(self, run_id: str, artifact_path: str, name: str) -> None:
        model_uri = f"runs:/{run_id}/{artifact_path}"
        mlflow.register_model(model_uri, name)

    def end_run(self) -> None:
        mlflow.end_run()
        self._run_id = None
```

- [ ] **Step 4: Run tests**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_tracker.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```
git add AlgoCore/services/ml/tracking/ AlgoCore/tests/services/ml/test_tracker.py
git commit -m "feat: add MLflow tracker wrapper (experiment logging + model registry)"
```

---

### Task 5: XGBoost Classifier

**Files:**
- Create: `AlgoCore/services/ml/models/__init__.py`
- Create: `AlgoCore/services/ml/models/xgboost_model.py`
- Create: `AlgoCore/tests/services/ml/test_xgboost_model.py`

**Interfaces:**
- Consumes: feature DataFrame from `build_features()` (columns = FEATURE_COLS, `target` col present)
- Produces:
  - `XGBoostModel()`
  - `.fit(df: pd.DataFrame) -> dict` — trains on df (uses `target` col), returns `{"accuracy": float, "sharpe": float}`
  - `.predict(df: pd.DataFrame) -> float` — confidence that next move is UP; range [0.0, 1.0]
  - `.save(path: str) -> None`
  - `.load(path: str) -> None`
  - `.is_trained -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# AlgoCore/tests/services/ml/test_xgboost_model.py
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta


def _make_feature_df(n: int = 80) -> pd.DataFrame:
    """Synthetic feature DataFrame matching build_features() output."""
    np.random.seed(42)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        rows.append({
            "rsi": float(np.random.uniform(20, 80)),
            "atr": float(np.random.uniform(10, 50)),
            "macd": float(np.random.uniform(-5, 5)),
            "macd_signal": float(np.random.uniform(-4, 4)),
            "macd_hist": float(np.random.uniform(-2, 2)),
            "bb_width": float(np.random.uniform(0.01, 0.05)),
            "returns": float(np.random.uniform(-0.005, 0.005)),
            "volume_ratio": float(np.random.uniform(0.5, 2.0)),
            "hour": float(i % 24),
            "dow": float(i % 7),
            "target": int(np.random.randint(0, 2)),
        })
    return pd.DataFrame(rows)


def test_xgboost_fit_returns_metrics():
    from services.ml.models.xgboost_model import XGBoostModel
    model = XGBoostModel()
    metrics = model.fit(_make_feature_df(80))
    assert "accuracy" in metrics and "sharpe" in metrics
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert isinstance(metrics["sharpe"], float)


def test_xgboost_predict_returns_float_in_range():
    from services.ml.models.xgboost_model import XGBoostModel
    model = XGBoostModel()
    df = _make_feature_df(80)
    model.fit(df)
    conf = model.predict(df.drop(columns=["target"]).iloc[-1:])
    assert 0.0 <= conf <= 1.0


def test_xgboost_is_trained_flag():
    from services.ml.models.xgboost_model import XGBoostModel
    model = XGBoostModel()
    assert not model.is_trained
    model.fit(_make_feature_df(80))
    assert model.is_trained


def test_xgboost_save_load(tmp_path):
    from services.ml.models.xgboost_model import XGBoostModel
    model = XGBoostModel()
    model.fit(_make_feature_df(80))
    path = str(tmp_path / "model.json")
    model.save(path)
    m2 = XGBoostModel()
    m2.load(path)
    assert m2.is_trained
```

- [ ] **Step 2: Run to verify failure**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_xgboost_model.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement XGBoostModel**

```python
# AlgoCore/services/ml/models/__init__.py  (empty)

# AlgoCore/services/ml/models/xgboost_model.py
import numpy as np
import pandas as pd
import xgboost as xgb
from services.ml.features import FEATURE_COLS


class XGBoostModel:
    def __init__(self):
        self._clf = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
        )
        self._trained = False

    @property
    def is_trained(self) -> bool:
        return self._trained

    def fit(self, df: pd.DataFrame) -> dict:
        """Train on df which must have FEATURE_COLS + 'target'."""
        X = df[FEATURE_COLS].values
        y = df["target"].values
        split = int(len(X) * 0.8)
        X_train, X_oos = X[:split], X[split:]
        y_train, y_oos = y[:split], y[split:]
        self._clf.fit(X_train, y_train)
        self._trained = True
        accuracy = float((self._clf.predict(X_oos) == y_oos).mean()) if len(X_oos) else 0.0
        sharpe   = self._calc_sharpe(y_oos, self._clf.predict_proba(X_oos)[:, 1]) if len(X_oos) else 0.0
        return {"accuracy": accuracy, "sharpe": sharpe}

    def predict(self, df: pd.DataFrame) -> float:
        """Return probability of upward move (confidence for BUY), range [0, 1]."""
        X = df[FEATURE_COLS].values
        return float(self._clf.predict_proba(X)[0, 1])

    def save(self, path: str) -> None:
        self._clf.save_model(path)

    def load(self, path: str) -> None:
        self._clf.load_model(path)
        self._trained = True

    @staticmethod
    def _calc_sharpe(y_true: np.ndarray, y_proba: np.ndarray) -> float:
        if len(y_true) == 0:
            return 0.0
        signals  = np.where(y_proba > 0.5, 1, -1)
        actual   = np.where(y_true == 1, 1, -1)
        returns  = signals * actual * 0.001      # 0.1% per bar proxy
        std      = returns.std()
        if std == 0:
            return 0.0
        # M15: 96 bars/day × 252 trading days
        return float(returns.mean() / std * np.sqrt(252 * 96))
```

- [ ] **Step 4: Run tests**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_xgboost_model.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add AlgoCore/services/ml/models/ AlgoCore/tests/services/ml/test_xgboost_model.py
git commit -m "feat: add XGBoost direction classifier with OOS Sharpe metric"
```

---

### Task 6: Training Pipeline

**Files:**
- Create: `AlgoCore/services/ml/training/__init__.py`
- Create: `AlgoCore/services/ml/training/pipeline.py`
- Create: `AlgoCore/tests/services/ml/test_pipeline.py`

**Interfaces:**
- Consumes: `OHLCVFetcher`, `build_features`, `XGBoostModel`, `MLflowTracker`, `settings.mlflow_tracking_uri`
- Produces: `TrainingPipeline(symbol, exchange, tracker)`
  - `.run(min_sharpe: float = 1.0) -> bool` — True if model promoted; False if Sharpe below threshold
  - Saves trained model to `AlgoCore/mlruns/<symbol>_xgb.json` as local artifact
  - Registers model in MLflow as `algocore-{symbol}-xgb` if promoted

- [ ] **Step 1: Write the failing tests**

```python
# AlgoCore/tests/services/ml/test_pipeline.py
from unittest.mock import MagicMock, patch
import pandas as pd


def _make_feature_df(n: int = 100) -> pd.DataFrame:
    import numpy as np
    np.random.seed(7)
    rows = [{"rsi": float(np.random.uniform(20,80)), "atr": float(np.random.uniform(10,50)),
             "macd": float(np.random.uniform(-5,5)), "macd_signal": float(np.random.uniform(-4,4)),
             "macd_hist": float(np.random.uniform(-2,2)), "bb_width": float(np.random.uniform(.01,.05)),
             "returns": float(np.random.uniform(-.005,.005)), "volume_ratio": float(np.random.uniform(.5,2)),
             "hour": float(i % 24), "dow": float(i % 7), "target": int(np.random.randint(0,2))}
            for i in range(n)]
    return pd.DataFrame(rows)


def test_pipeline_run_returns_true_when_sharpe_passes():
    mock_fetcher = MagicMock()
    mock_fetcher.get_candles.return_value = pd.DataFrame(
        {"timestamp": ["t"] * 5, "open": [1.0]*5, "high": [1.0]*5,
         "low": [1.0]*5, "close": [1.0]*5, "volume": [1.0]*5})
    mock_model = MagicMock()
    mock_model.fit.return_value = {"accuracy": 0.65, "sharpe": 1.5}
    mock_model.is_trained = True
    mock_tracker = MagicMock()

    with patch("services.ml.training.pipeline.build_features", return_value=_make_feature_df()):
        from services.ml.training.pipeline import TrainingPipeline
        pipeline = TrainingPipeline("ETHUSDT", "bitget", mock_tracker,
                                    fetcher=mock_fetcher, model=mock_model)
        result = pipeline.run(min_sharpe=1.0)
    assert result is True
    mock_tracker.start_run.assert_called_once()
    mock_tracker.log_metrics.assert_called_once()
    mock_tracker.register_model.assert_called_once()


def test_pipeline_run_returns_false_when_sharpe_fails():
    mock_fetcher = MagicMock()
    mock_fetcher.get_candles.return_value = pd.DataFrame(
        {"timestamp": ["t"]*5, "open":[1.0]*5, "high":[1.0]*5,
         "low":[1.0]*5, "close":[1.0]*5, "volume":[1.0]*5})
    mock_model = MagicMock()
    mock_model.fit.return_value = {"accuracy": 0.50, "sharpe": 0.3}
    mock_model.is_trained = True
    mock_tracker = MagicMock()

    with patch("services.ml.training.pipeline.build_features", return_value=_make_feature_df()):
        from services.ml.training.pipeline import TrainingPipeline
        pipeline = TrainingPipeline("ETHUSDT", "bitget", mock_tracker,
                                    fetcher=mock_fetcher, model=mock_model)
        result = pipeline.run(min_sharpe=1.0)
    assert result is False
    mock_tracker.register_model.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_pipeline.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement TrainingPipeline**

```python
# AlgoCore/services/ml/training/__init__.py  (empty)

# AlgoCore/services/ml/training/pipeline.py
import os
from services.ml.data.fetcher import OHLCVFetcher
from services.ml.features import build_features
from services.ml.models.xgboost_model import XGBoostModel
from services.ml.tracking.mlflow_tracker import MLflowTracker


class TrainingPipeline:
    _ARTIFACT = "xgb_model"

    def __init__(
        self,
        symbol: str,
        exchange: str,
        tracker: MLflowTracker,
        fetcher: OHLCVFetcher | None = None,
        model: XGBoostModel | None = None,
    ):
        self._symbol   = symbol
        self._exchange = exchange
        self._tracker  = tracker
        self._fetcher  = fetcher or OHLCVFetcher()
        self._model    = model  or XGBoostModel()

    def run(self, min_sharpe: float = 1.0) -> bool:
        """Fetch → build features → train → validate Sharpe → promote if passes."""
        raw = self._fetcher.get_candles(self._symbol, exchange=self._exchange, limit=500)
        df  = build_features(raw)

        run_id = self._tracker.start_run(f"{self._symbol}_xgb")
        self._tracker.log_params({
            "symbol": self._symbol, "exchange": self._exchange,
            "n_rows": len(df), "min_sharpe": min_sharpe,
        })

        metrics = self._model.fit(df)
        self._tracker.log_metrics(metrics)

        promoted = metrics["sharpe"] >= min_sharpe
        if promoted:
            self._tracker.log_model(self._model._clf, self._ARTIFACT)
            reg_name = f"algocore-{self._symbol.lower()}-xgb"
            self._tracker.register_model(run_id, self._ARTIFACT, reg_name)
            print(f"[Pipeline] {self._symbol} promoted: Sharpe={metrics['sharpe']:.3f}")
        else:
            print(f"[Pipeline] {self._symbol} not promoted: Sharpe={metrics['sharpe']:.3f} < {min_sharpe}")

        self._tracker.end_run()
        return promoted
```

- [ ] **Step 4: Run tests**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_pipeline.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```
git add AlgoCore/services/ml/training/ AlgoCore/tests/services/ml/test_pipeline.py
git commit -m "feat: add training pipeline (fetch→features→XGBoost→Sharpe OOS→MLflow promote)"
```

---

### Task 7: ML Inference + ML Service Loop

**Files:**
- Create: `AlgoCore/services/ml/inference/__init__.py`
- Create: `AlgoCore/services/ml/inference/predictor.py`
- Create: `AlgoCore/services/ml/service.py`
- Create: `AlgoCore/tests/services/ml/test_predictor.py`

**Interfaces:**
- Consumes: `XGBoostModel`, `OHLCVFetcher`, `build_features`, `publish`, `events.ML_SIGNAL`, `Signal` model
- Produces:
  - `Predictor(model: XGBoostModel)`
  - `.predict_from_df(df: pd.DataFrame) -> tuple[str, float]` — `("BUY"|"SELL"|"HOLD", confidence)`
    - confidence > 0.6 → "BUY"
    - confidence < 0.4 → "SELL"
    - otherwise → "HOLD"
  - `MLService(symbol, exchange, model_path)` — runs every 15 minutes, publishes `Signal` to `events.ML_SIGNAL`

- [ ] **Step 1: Write the failing tests**

```python
# AlgoCore/tests/services/ml/test_predictor.py
from unittest.mock import MagicMock, patch
import pandas as pd


def _make_feature_row() -> pd.DataFrame:
    return pd.DataFrame([{
        "rsi": 45.0, "atr": 20.0, "macd": 0.5, "macd_signal": 0.3,
        "macd_hist": 0.2, "bb_width": 0.02, "returns": 0.001,
        "volume_ratio": 1.1, "hour": 10.0, "dow": 2.0,
    }])


def test_predictor_buy_signal():
    from services.ml.inference.predictor import Predictor
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.75  # > 0.6 → BUY
    pred = Predictor(mock_model)
    action, conf = pred.predict_from_df(_make_feature_row())
    assert action == "BUY"
    assert conf == 0.75


def test_predictor_sell_signal():
    from services.ml.inference.predictor import Predictor
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.30  # < 0.4 → SELL
    pred = Predictor(mock_model)
    action, conf = pred.predict_from_df(_make_feature_row())
    assert action == "SELL"
    assert conf == 0.30


def test_predictor_hold_signal():
    from services.ml.inference.predictor import Predictor
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.50  # 0.4–0.6 → HOLD
    pred = Predictor(mock_model)
    action, conf = pred.predict_from_df(_make_feature_row())
    assert action == "HOLD"
    assert conf == 0.50


def test_ml_service_publishes_signal():
    import pandas as pd
    raw_df = pd.DataFrame({
        "timestamp": ["2026-01-01T00:00:00+00:00"] * 60,
        "open": [3000.0] * 60, "high": [3010.0] * 60,
        "low": [2990.0] * 60, "close": [3005.0] * 60, "volume": [1000.0] * 60,
    })
    mock_model = MagicMock()
    mock_model.is_trained = True
    mock_model.predict.return_value = 0.70

    with patch("services.ml.service.OHLCVFetcher") as MockFetcher, \
         patch("services.ml.service.XGBoostModel", return_value=mock_model), \
         patch("services.ml.service.publish") as mock_publish:
        MockFetcher.return_value.get_candles.return_value = raw_df
        from services.ml.service import MLService
        svc = MLService("ETHUSDT", "bitget", model_path=None)
        svc._run_once()
    mock_publish.assert_called_once()
    args = mock_publish.call_args
    assert args[0][0] == "ml:signal"
    payload = args[0][1]
    assert payload["action"] == "BUY"
    assert payload["symbol"] == "ETHUSDT"
```

- [ ] **Step 2: Run to verify failure**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_predictor.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement Predictor and MLService**

```python
# AlgoCore/services/ml/inference/__init__.py  (empty)

# AlgoCore/services/ml/inference/predictor.py
from services.ml.models.xgboost_model import XGBoostModel
import pandas as pd


class Predictor:
    BUY_THRESHOLD  = 0.6
    SELL_THRESHOLD = 0.4

    def __init__(self, model: XGBoostModel):
        self._model = model

    def predict_from_df(self, df: pd.DataFrame) -> tuple[str, float]:
        """
        Returns (action, confidence).
        confidence > 0.6 → BUY, < 0.4 → SELL, else HOLD.
        """
        conf = self._model.predict(df)
        if conf > self.BUY_THRESHOLD:
            return "BUY", conf
        if conf < self.SELL_THRESHOLD:
            return "SELL", conf
        return "HOLD", conf
```

```python
# AlgoCore/services/ml/service.py
import time
from datetime import datetime, timezone

from shared import events
from shared.state import publish
from services.ml.data.fetcher import OHLCVFetcher
from services.ml.features import build_features
from services.ml.models.xgboost_model import XGBoostModel
from services.ml.inference.predictor import Predictor


class MLService:
    INTERVAL_SEC = 900  # 15 minutes

    def __init__(self, symbol: str, exchange: str, model_path: str | None = None):
        self._symbol    = symbol
        self._exchange  = exchange
        self._fetcher   = OHLCVFetcher()
        self._model     = XGBoostModel()
        if model_path:
            self._model.load(model_path)
        self._predictor = Predictor(self._model)

    def _run_once(self) -> None:
        try:
            raw = self._fetcher.get_candles(self._symbol, exchange=self._exchange, limit=200)
            df  = build_features(raw)
            if df.empty or not self._model.is_trained:
                print(f"[MLService] {self._symbol}: not enough data or model not trained")
                return
            features = df.drop(columns=["target"], errors="ignore")
            action, conf = self._predictor.predict_from_df(features.iloc[-1:])
            payload = {
                "symbol":     self._symbol,
                "action":     action,
                "confidence": round(conf, 4),
                "strategy":   "ml:xgboost",
                "exchange":   self._exchange,
                "timestamp":  datetime.now(timezone.utc).isoformat(),
            }
            publish(events.ML_SIGNAL, payload)
            print(f"[MLService] {self._symbol}: {action} conf={conf:.3f}")
        except Exception as e:
            print(f"[MLService] error: {e}")

    def run(self) -> None:
        print(f"[MLService] Starting for {self._symbol} on {self._exchange}")
        while True:
            self._run_once()
            time.sleep(self.INTERVAL_SEC)
```

- [ ] **Step 4: Run tests**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_predictor.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add AlgoCore/services/ml/inference/ AlgoCore/services/ml/service.py AlgoCore/tests/services/ml/test_predictor.py
git commit -m "feat: add ML inference predictor and 15-min ML service loop"
```

---

### Task 8: Orchestrator Service

**Files:**
- Create: `AlgoCore/services/orchestrator/__init__.py`
- Create: `AlgoCore/services/orchestrator/context.py`
- Create: `AlgoCore/services/orchestrator/tools.py`
- Create: `AlgoCore/services/orchestrator/rules.py`
- Create: `AlgoCore/services/orchestrator/agent.py`
- Create: `AlgoCore/services/orchestrator/service.py`
- Create: `AlgoCore/tests/services/orchestrator/__init__.py`
- Create: `AlgoCore/tests/services/orchestrator/test_rules.py`
- Create: `AlgoCore/tests/services/orchestrator/test_agent.py`

**Interfaces:**
- Consumes: `get_state("risk")` → `RiskState`, `subscribe_once(events.ML_SIGNAL)` → list of signal dicts, `subscribe_once(events.PRICE_TICK)` → list of tick dicts, `publish(events.ORCH_DECISION, ...)`, `settings.anthropic_api_key`, `settings.gemini_api_key`
- Produces:
  - `rules.py`: `apply_rules(risk: dict, signals: list[dict]) -> dict` — deterministic fallback; returns `OrchestratorDecision.model_dump()`
  - `agent.py`: `OrchestratorAgent(anthropic_key, gemini_key)`, `.decide(context: str) -> dict`
  - `service.py`: `OrchestratorService()`, `.run()` — loops every 15 min

- [ ] **Step 1: Write the failing tests**

```python
# AlgoCore/tests/services/orchestrator/test_rules.py
def test_rules_stop_all_on_drawdown():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 7.0, "is_stopped": True, "exposure_pct": 50.0}
    decision = apply_rules(risk, [])
    assert decision["action"] == "STOP_ALL"


def test_rules_pause_on_high_drawdown():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 4.5, "is_stopped": False, "exposure_pct": 50.0}
    decision = apply_rules(risk, [])
    assert decision["action"] == "PAUSE_STRATEGY"


def test_rules_hold_on_normal_conditions():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 1.0, "is_stopped": False, "exposure_pct": 30.0}
    decision = apply_rules(risk, [])
    assert decision["action"] == "HOLD"


def test_rules_buy_on_high_confidence_ml_signal():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 0.5, "is_stopped": False, "exposure_pct": 20.0}
    signals = [{"action": "BUY", "confidence": 0.85, "symbol": "ETHUSDT"}]
    decision = apply_rules(risk, signals)
    assert decision["action"] == "BUY"
```

```python
# AlgoCore/tests/services/orchestrator/test_agent.py
from unittest.mock import MagicMock, patch


def test_agent_falls_back_to_rules_when_no_api_keys():
    from services.orchestrator.agent import OrchestratorAgent
    agent = OrchestratorAgent(anthropic_key="", gemini_key="")
    result = agent.decide(
        context="test",
        risk={"drawdown_pct": 1.0, "is_stopped": False, "exposure_pct": 20.0},
        signals=[],
    )
    assert "action" in result
    assert result["action"] in {"HOLD", "BUY", "SELL", "PAUSE_STRATEGY",
                                 "RESUME_ALL", "STOP_ALL", "ADJUST_POSITION"}


def test_agent_uses_claude_when_key_available():
    mock_client = MagicMock()
    mock_block  = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "set_trading_action"
    mock_block.input = {"action": "HOLD", "reason": "test", "confidence": 0.8,
                        "market": "crypto", "exchange": "auto", "strategy": "ml",
                        "capital_pct": 0.0}
    mock_client.messages.create.return_value.content = [mock_block]

    with patch("services.orchestrator.agent.Anthropic", return_value=mock_client):
        from services.orchestrator.agent import OrchestratorAgent
        agent = OrchestratorAgent(anthropic_key="sk-test", gemini_key="")
        result = agent.decide(
            context="test",
            risk={"drawdown_pct": 1.0, "is_stopped": False, "exposure_pct": 20.0},
            signals=[],
        )
    assert result["action"] == "HOLD"
    assert result["confidence"] == 0.8
```

- [ ] **Step 2: Run to verify failure**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/orchestrator/ -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement orchestrator modules**

```python
# AlgoCore/services/orchestrator/__init__.py  (empty)
# AlgoCore/tests/services/orchestrator/__init__.py  (empty)
```

```python
# AlgoCore/services/orchestrator/tools.py
TOOLS = [
    {
        "name": "set_trading_action",
        "description": "Define the trading action. Call ALWAYS with the final decision after analyzing market state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["HOLD", "BUY", "SELL", "ADJUST_POSITION",
                             "PAUSE_STRATEGY", "RESUME_ALL", "STOP_ALL"],
                },
                "market":      {"type": "string", "enum": ["crypto", "forex", "both"]},
                "exchange":    {"type": "string", "enum": ["bitget", "binance", "mt5", "auto"]},
                "strategy":    {"type": "string", "enum": ["grid", "rsi", "ml", "rl", "technical"]},
                "capital_pct": {"type": "number"},
                "reason":      {"type": "string"},
                "confidence":  {"type": "number"},
            },
            "required": ["action", "reason", "confidence"],
        },
    }
]

SYSTEM_PROMPT = """You are a quantitative risk manager for an algorithmic trading system operating
on Bitget, Binance (crypto) and MT5 (forex/XAUUSD). You receive market state + ML model signals
and decide the optimal trading action. Principles:
1. Capital preservation first — when in doubt, HOLD.
2. Drawdown >4%: PAUSE_STRATEGY. Drawdown >6%: STOP_ALL.
3. High-confidence ML signal (>0.75) with low drawdown (<2%): consider BUY or SELL.
4. Respond ALWAYS using the set_trading_action tool."""
```

```python
# AlgoCore/services/orchestrator/context.py
from shared.state import get_state, subscribe_once
from shared import events


def build_context(last_signal_id: str = "0") -> tuple[str, dict, list[dict]]:
    """
    Build prompt context from Redis.

    Returns:
        (prompt_text, risk_dict, ml_signals_list)
    """
    risk_raw = get_state("risk") or {}
    risk = {
        "drawdown_pct":  risk_raw.get("drawdown_pct", 0.0),
        "is_stopped":    risk_raw.get("is_stopped", False),
        "exposure_pct":  risk_raw.get("exposure_pct", 0.0),
        "daily_pnl_pct": risk_raw.get("daily_pnl_pct", 0.0),
        "open_positions": risk_raw.get("open_positions", 0),
    }
    ml_signals = subscribe_once(events.ML_SIGNAL, last_id=last_signal_id)
    prices_raw = subscribe_once(events.PRICE_TICK, last_id="0")
    prices = {p["symbol"]: p["price"] for p in prices_raw[-5:]} if prices_raw else {}

    signal_summary = ""
    for s in ml_signals:
        signal_summary += (
            f"  {s.get('symbol')}: {s.get('action')} "
            f"conf={s.get('confidence', 0):.2f} strategy={s.get('strategy')}\n"
        )
    if not signal_summary:
        signal_summary = "  No ML signals yet.\n"

    price_summary = ", ".join(f"{k}=${v:.2f}" for k, v in prices.items()) or "no price data"

    prompt = f"""=== MARKET STATE ===
Prices: {price_summary}

=== RISK ===
Drawdown: {risk['drawdown_pct']:.2f}%  Exposure: {risk['exposure_pct']:.1f}%
Daily P&L: {risk['daily_pnl_pct']:+.2f}%  Stopped: {risk['is_stopped']}
Open positions: {risk['open_positions']}

=== ML SIGNALS (last 15 min) ===
{signal_summary}
Analyze the above and call set_trading_action with your decision."""

    return prompt, risk, ml_signals
```

```python
# AlgoCore/services/orchestrator/rules.py

def apply_rules(risk: dict, signals: list[dict]) -> dict:
    """Deterministic fallback — no LLM required."""
    dd  = float(risk.get("drawdown_pct", 0))
    stopped = bool(risk.get("is_stopped", False))

    if stopped or dd >= 6.0:
        return _decision("STOP_ALL", "Drawdown ≥6% or system stopped.", 0.99)
    if dd >= 4.0:
        return _decision("PAUSE_STRATEGY", "Drawdown ≥4%: pausing ML/RL strategies.", 0.9)
    if dd >= 2.0:
        return _decision("HOLD", "Drawdown ≥2%: conservative hold.", 0.8)

    # Act on high-confidence ML signal
    for sig in signals:
        conf = float(sig.get("confidence", 0))
        action = sig.get("action", "HOLD")
        if action == "BUY"  and conf >= 0.75:
            return _decision("BUY",  f"ML BUY signal conf={conf:.2f}.", conf)
        if action == "SELL" and conf >= 0.75:
            return _decision("SELL", f"ML SELL signal conf={conf:.2f}.", conf)

    return _decision("HOLD", "No strong signal — holding current positions.", 0.6)


def _decision(action: str, reason: str, confidence: float) -> dict:
    return {
        "action": action, "market": "crypto", "exchange": "auto",
        "strategy": "ml", "capital_pct": 0.0,
        "reason": reason, "confidence": confidence,
    }
```

```python
# AlgoCore/services/orchestrator/agent.py
import json
import requests as req
from anthropic import Anthropic
from services.orchestrator.tools import TOOLS, SYSTEM_PROMPT
from services.orchestrator.rules import apply_rules

MODEL_CLAUDE = "claude-haiku-4-5-20251001"
MODEL_GEMINI = "gemini-2.0-flash"
GEMINI_URL   = ("https://generativelanguage.googleapis.com/v1beta/models/"
                f"{MODEL_GEMINI}:generateContent")


class OrchestratorAgent:
    def __init__(self, anthropic_key: str, gemini_key: str):
        self._claude = Anthropic(api_key=anthropic_key) if anthropic_key else None
        self._gemini_key = gemini_key

    def decide(self, context: str, risk: dict, signals: list[dict]) -> dict:
        # 1. Try Claude Haiku
        if self._claude:
            try:
                resp = self._claude.messages.create(
                    model=MODEL_CLAUDE,
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": context}],
                    tools=TOOLS,
                    tool_choice={"type": "any"},
                )
                for block in resp.content:
                    if block.type == "tool_use" and block.name == "set_trading_action":
                        print("[Orchestrator] Decision via Claude Haiku")
                        return block.input
            except Exception as e:
                print(f"[Orchestrator] Claude unavailable ({e}) — trying Gemini")

        # 2. Try Gemini Flash
        if self._gemini_key:
            result = self._call_gemini(context)
            if result:
                print("[Orchestrator] Decision via Gemini Flash")
                return result

        # 3. Deterministic fallback
        print("[Orchestrator] Using deterministic rules fallback")
        return apply_rules(risk, signals)

    def _call_gemini(self, context: str) -> dict | None:
        prompt = (
            SYSTEM_PROMPT + "\n\n" + context +
            '\n\nRespond ONLY with valid JSON:\n'
            '{"action":"HOLD|BUY|SELL|ADJUST_POSITION|PAUSE_STRATEGY|RESUME_ALL|STOP_ALL",'
            '"market":"crypto|forex|both","exchange":"bitget|binance|mt5|auto",'
            '"strategy":"grid|rsi|ml|rl|technical","capital_pct":0.0,'
            '"reason":"string","confidence":0.0}'
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300},
        }
        try:
            r = req.post(f"{GEMINI_URL}?key={self._gemini_key}", json=body, timeout=15)
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception as e:
            print(f"[Orchestrator] Gemini error: {e}")
            return None
```

```python
# AlgoCore/services/orchestrator/service.py
import time
from datetime import datetime, timezone

from shared import events
from shared.config import settings
from shared.state import publish
from services.orchestrator.context import build_context
from services.orchestrator.agent import OrchestratorAgent


class OrchestratorService:
    INTERVAL_SEC = 900  # 15 minutes

    def __init__(self):
        self._agent = OrchestratorAgent(
            anthropic_key=settings.anthropic_api_key,
            gemini_key=settings.gemini_api_key,
        )
        self._last_signal_id = "0"

    def _run_once(self) -> None:
        try:
            context, risk, signals = build_context(self._last_signal_id)
            decision = self._agent.decide(context, risk, signals)
            decision["timestamp"] = datetime.now(timezone.utc).isoformat()
            publish(events.ORCH_DECISION, decision)
            print(f"[Orchestrator] {decision['action']} — {decision['reason'][:60]}")
        except Exception as e:
            print(f"[Orchestrator] error: {e}")

    def run(self) -> None:
        print("[Orchestrator] Starting 15-min decision loop")
        while True:
            self._run_once()
            time.sleep(self.INTERVAL_SEC)
```

- [ ] **Step 4: Run tests**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/orchestrator/ -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```
git add AlgoCore/services/orchestrator/ AlgoCore/tests/services/orchestrator/
git commit -m "feat: add orchestrator service (Claude Haiku → Gemini → deterministic rules)"
```

---

### Task 9: Telegram Notifications

**Files:**
- Create: `AlgoCore/services/notifications/__init__.py`
- Create: `AlgoCore/services/notifications/telegram.py`
- Create: `AlgoCore/services/notifications/alerts.py`
- Create: `AlgoCore/tests/services/notifications/__init__.py`
- Create: `AlgoCore/tests/services/notifications/test_telegram.py`

**Interfaces:**
- Consumes: `settings.telegram_bot_token`, `settings.telegram_chat_id`, `subscribe_once`, `events.RISK_ALERT`, `events.ORDER_FILLED`, `events.ORCH_DECISION`
- Produces:
  - `TelegramClient(token, chat_id)`, `.send(message: str) -> bool`
  - `AlertSubscriber(client)`, `.listen()` — infinite loop subscribing to Redis events

- [ ] **Step 1: Write the failing tests**

```python
# AlgoCore/tests/services/notifications/test_telegram.py
from unittest.mock import patch, MagicMock


def test_telegram_client_send_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    with patch("services.notifications.telegram.requests.post", return_value=mock_resp):
        from services.notifications.telegram import TelegramClient
        client = TelegramClient("bot123", "chat456")
        result = client.send("Hello AlgoCore!")
    assert result is True


def test_telegram_client_send_failure_returns_false():
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"ok": False, "description": "Bad Request"}
    with patch("services.notifications.telegram.requests.post", return_value=mock_resp):
        from services.notifications.telegram import TelegramClient
        client = TelegramClient("bad-token", "chat")
        result = client.send("test")
    assert result is False


def test_telegram_client_send_exception_returns_false():
    with patch("services.notifications.telegram.requests.post", side_effect=Exception("network")):
        from services.notifications.telegram import TelegramClient
        client = TelegramClient("t", "c")
        result = client.send("test")
    assert result is False


def test_alert_subscriber_sends_on_risk_alert():
    from unittest.mock import call
    risk_payload = {"level": "STOP", "drawdown_pct": 7.0}
    order_payload = {"symbol": "ETHUSDT", "action": "BUY", "price": 3200.0}

    call_count = [0]

    def fake_subscribe(channel, last_id="0"):
        call_count[0] += 1
        if call_count[0] == 1 and channel == "risk:alert":
            return [risk_payload]
        return []

    mock_client = MagicMock()
    mock_client.send.return_value = True

    with patch("services.notifications.alerts.subscribe_once", side_effect=fake_subscribe), \
         patch("services.notifications.alerts.time.sleep"):
        from services.notifications.alerts import AlertSubscriber
        sub = AlertSubscriber(mock_client, max_iterations=1)
        sub.listen()

    assert mock_client.send.called
    sent_msg = mock_client.send.call_args[0][0]
    assert "STOP" in sent_msg or "risk" in sent_msg.lower()
```

- [ ] **Step 2: Run to verify failure**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/notifications/test_telegram.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement Telegram client and alert subscriber**

```python
# AlgoCore/services/notifications/__init__.py  (empty)
# AlgoCore/tests/services/notifications/__init__.py  (empty)
```

```python
# AlgoCore/services/notifications/telegram.py
import requests

TELEGRAM_API = "https://api.telegram.org"


class TelegramClient:
    def __init__(self, token: str, chat_id: str):
        self._token   = token
        self._chat_id = chat_id

    def send(self, message: str) -> bool:
        if not self._token or not self._chat_id:
            return False
        try:
            r = requests.post(
                f"{TELEGRAM_API}/bot{self._token}/sendMessage",
                json={"chat_id": self._chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
            return r.json().get("ok", False)
        except Exception as e:
            print(f"[Telegram] send error: {e}")
            return False
```

```python
# AlgoCore/services/notifications/alerts.py
import time
from shared import events
from shared.state import subscribe_once
from services.notifications.telegram import TelegramClient


class AlertSubscriber:
    POLL_SEC = 5

    def __init__(self, client: TelegramClient, max_iterations: int | None = None):
        self._client     = client
        self._max_iter   = max_iterations
        self._last_ids   = {
            events.RISK_ALERT:    "0",
            events.ORDER_FILLED:  "0",
            events.ORCH_DECISION: "0",
        }

    def listen(self) -> None:
        print("[Alerts] Starting Telegram alert subscriber")
        iterations = 0
        while self._max_iter is None or iterations < self._max_iter:
            self._poll()
            time.sleep(self.POLL_SEC)
            iterations += 1

    def _poll(self) -> None:
        for channel, last_id in self._last_ids.items():
            for payload in subscribe_once(channel, last_id=last_id):
                msg = self._format(channel, payload)
                if msg:
                    self._client.send(msg)

    @staticmethod
    def _format(channel: str, payload: dict) -> str | None:
        if channel == events.RISK_ALERT:
            level = payload.get("level", "")
            dd    = payload.get("drawdown_pct", 0)
            return f"⚠️ <b>RISK ALERT — {level}</b>\nDrawdown: {dd:.2f}%"
        if channel == events.ORDER_FILLED:
            sym  = payload.get("symbol", "?")
            side = payload.get("side", "?").upper()
            px   = payload.get("price", 0)
            return f"✅ <b>ORDER FILLED</b>\n{sym} {side} @ ${px:.2f}"
        if channel == events.ORCH_DECISION:
            action = payload.get("action", "?")
            reason = payload.get("reason", "")
            conf   = payload.get("confidence", 0)
            if action in ("STOP_ALL", "PAUSE_STRATEGY"):
                return f"🔴 <b>ORCHESTRATOR: {action}</b>\n{reason}\nConf: {conf:.0%}"
            return None  # only alert on significant decisions
        return None
```

- [ ] **Step 4: Run tests**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/notifications/test_telegram.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add AlgoCore/services/notifications/ AlgoCore/tests/services/notifications/
git commit -m "feat: add Telegram notification service (risk alerts, fills, orchestrator decisions)"
```

---

### Task 10: LSTM Model + Ensemble (PyTorch)

**Files:**
- Create: `AlgoCore/services/ml/models/lstm_model.py`
- Create: `AlgoCore/services/ml/models/ensemble.py`
- Modify: `AlgoCore/requirements.txt` (add torch)

**Interfaces:**
- Consumes: feature DataFrame from `build_features()`, `FEATURE_COLS` (10 features)
- Produces:
  - `LSTMModel(input_size=10, hidden_size=64, num_layers=2, seq_len=20)`
  - `.fit(df: pd.DataFrame, epochs: int = 30) -> dict` — `{"accuracy": float, "sharpe": float}`
  - `.predict(df: pd.DataFrame) -> float` — uses last `seq_len` rows; returns confidence [0, 1]
  - `.save(path: str) -> None` / `.load(path: str) -> None` / `.is_trained -> bool`
  - `EnsembleModel(xgb: XGBoostModel, lstm: LSTMModel, weights: tuple[float, float] = (0.6, 0.4))`
  - `.predict(df: pd.DataFrame) -> float` — weighted average; uses last row for XGB, last seq_len for LSTM

- [ ] **Step 1: Add torch to requirements.txt**

Append to `AlgoCore/requirements.txt`:
```
torch==2.3.1
```

Install: `pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu`
(CPU-only build — ~250 MB, no CUDA needed for training at this scale)

- [ ] **Step 2: Write the failing tests**

```python
# AlgoCore/tests/services/ml/test_lstm_model.py  (new file)
import pandas as pd
import numpy as np


def _make_feature_df(n: int = 60) -> pd.DataFrame:
    np.random.seed(99)
    rows = [{"rsi": float(np.random.uniform(20,80)), "atr": float(np.random.uniform(10,50)),
             "macd": float(np.random.uniform(-5,5)), "macd_signal": float(np.random.uniform(-4,4)),
             "macd_hist": float(np.random.uniform(-2,2)), "bb_width": float(np.random.uniform(.01,.05)),
             "returns": float(np.random.uniform(-.005,.005)), "volume_ratio": float(np.random.uniform(.5,2)),
             "hour": float(i%24), "dow": float(i%7), "target": int(np.random.randint(0,2))}
            for i in range(n)]
    return pd.DataFrame(rows)


def test_lstm_fit_returns_metrics():
    from services.ml.models.lstm_model import LSTMModel
    model = LSTMModel(input_size=10, hidden_size=32, num_layers=1, seq_len=10)
    metrics = model.fit(_make_feature_df(60), epochs=2)
    assert "accuracy" in metrics and "sharpe" in metrics


def test_lstm_predict_returns_float_in_range():
    from services.ml.models.lstm_model import LSTMModel
    model = LSTMModel(input_size=10, hidden_size=32, num_layers=1, seq_len=10)
    df = _make_feature_df(60)
    model.fit(df, epochs=2)
    conf = model.predict(df.drop(columns=["target"]))
    assert 0.0 <= conf <= 1.0


def test_lstm_is_trained_flag():
    from services.ml.models.lstm_model import LSTMModel
    model = LSTMModel(input_size=10, hidden_size=32, num_layers=1, seq_len=5)
    assert not model.is_trained
    model.fit(_make_feature_df(40), epochs=1)
    assert model.is_trained


def test_ensemble_predict_in_range():
    from services.ml.models.xgboost_model import XGBoostModel
    from services.ml.models.lstm_model import LSTMModel
    from services.ml.models.ensemble import EnsembleModel
    df = _make_feature_df(80)
    xgb = XGBoostModel()
    xgb.fit(df)
    lstm = LSTMModel(input_size=10, hidden_size=32, num_layers=1, seq_len=10)
    lstm.fit(df, epochs=1)
    ens = EnsembleModel(xgb, lstm, weights=(0.6, 0.4))
    conf = ens.predict(df.drop(columns=["target"]))
    assert 0.0 <= conf <= 1.0
```

- [ ] **Step 3: Run to verify failure**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_lstm_model.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Implement LSTMModel**

```python
# AlgoCore/services/ml/models/lstm_model.py
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from services.ml.features import FEATURE_COLS


class _LSTMNet(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc   = nn.Linear(hidden_size, 1)
        self.sig  = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.sig(self.fc(out[:, -1, :]))


class LSTMModel:
    def __init__(self, input_size: int = 10, hidden_size: int = 64,
                 num_layers: int = 2, seq_len: int = 20):
        self._net      = _LSTMNet(input_size, hidden_size, num_layers)
        self._seq_len  = seq_len
        self._trained  = False

    @property
    def is_trained(self) -> bool:
        return self._trained

    def fit(self, df: pd.DataFrame, epochs: int = 30) -> dict:
        X, y = self._make_sequences(df)
        if len(X) == 0:
            return {"accuracy": 0.0, "sharpe": 0.0}
        split    = int(len(X) * 0.8)
        X_t, y_t = torch.FloatTensor(X[:split]), torch.FloatTensor(y[:split]).unsqueeze(1)
        X_v, y_v = torch.FloatTensor(X[split:]), torch.FloatTensor(y[split:])
        opt   = torch.optim.Adam(self._net.parameters(), lr=1e-3)
        loss_fn = nn.BCELoss()
        self._net.train()
        for _ in range(epochs):
            opt.zero_grad()
            pred = self._net(X_t)
            loss_fn(pred, y_t).backward()
            opt.step()
        self._trained = True
        self._net.eval()
        with torch.no_grad():
            proba = self._net(torch.FloatTensor(X[split:])).squeeze().numpy()
        if proba.ndim == 0:
            proba = np.array([float(proba)])
        preds  = (proba > 0.5).astype(int)
        acc    = float((preds == y_v.numpy()).mean()) if len(preds) else 0.0
        sharpe = self._calc_sharpe(y_v.numpy(), proba)
        return {"accuracy": acc, "sharpe": sharpe}

    def predict(self, df: pd.DataFrame) -> float:
        """Use last seq_len rows from df (no target column)."""
        X, _ = self._make_sequences(df, has_target=False)
        if len(X) == 0:
            return 0.5
        self._net.eval()
        with torch.no_grad():
            return float(self._net(torch.FloatTensor(X[-1:])).squeeze())

    def save(self, path: str) -> None:
        torch.save(self._net.state_dict(), path)

    def load(self, path: str) -> None:
        self._net.load_state_dict(torch.load(path, weights_only=True))
        self._trained = True

    def _make_sequences(self, df: pd.DataFrame, has_target: bool = True):
        cols = FEATURE_COLS
        X_raw = df[cols].values.astype(float)
        y_raw = df["target"].values.astype(float) if has_target and "target" in df.columns else None
        seqs, targets = [], []
        for i in range(self._seq_len, len(X_raw)):
            seqs.append(X_raw[i - self._seq_len:i])
            if y_raw is not None:
                targets.append(y_raw[i])
        return np.array(seqs), np.array(targets)

    @staticmethod
    def _calc_sharpe(y_true: np.ndarray, y_proba: np.ndarray) -> float:
        if len(y_true) == 0:
            return 0.0
        signals = np.where(y_proba > 0.5, 1, -1)
        actual  = np.where(y_true == 1, 1, -1)
        returns = signals * actual * 0.001
        std = returns.std()
        return float(returns.mean() / std * np.sqrt(252 * 96)) if std > 0 else 0.0
```

- [ ] **Step 5: Implement EnsembleModel**

```python
# AlgoCore/services/ml/models/ensemble.py
import pandas as pd
from services.ml.models.xgboost_model import XGBoostModel
from services.ml.models.lstm_model import LSTMModel


class EnsembleModel:
    def __init__(
        self,
        xgb: XGBoostModel,
        lstm: LSTMModel,
        weights: tuple[float, float] = (0.6, 0.4),
    ):
        self._xgb     = xgb
        self._lstm    = lstm
        self._w_xgb   = weights[0]
        self._w_lstm  = weights[1]

    def predict(self, df: pd.DataFrame) -> float:
        """
        Weighted average of XGBoost (last row) and LSTM (last seq_len rows).
        Falls back to XGBoost only if LSTM not trained.
        """
        xgb_conf = self._xgb.predict(df.iloc[-1:])
        if not self._lstm.is_trained:
            return xgb_conf
        lstm_conf = self._lstm.predict(df)
        return self._w_xgb * xgb_conf + self._w_lstm * lstm_conf
```

- [ ] **Step 6: Run tests**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/services/ml/test_lstm_model.py -v
```
Expected: 4 passed

- [ ] **Step 7: Commit**

```
git add AlgoCore/services/ml/models/lstm_model.py AlgoCore/services/ml/models/ensemble.py AlgoCore/requirements.txt AlgoCore/tests/services/ml/test_lstm_model.py
git commit -m "feat: add LSTM model (PyTorch) and ensemble combiner (XGBoost 60% + LSTM 40%)"
```

---

### Task 11: Phase 2 Integration Smoke Test

**Files:**
- Create: `AlgoCore/tests/test_integration_ml.py`

**Interfaces:**
- Imports all Phase 2 modules without error
- Verifies feature→predict flow end-to-end with mocks
- Verifies orchestrator rules flow

- [ ] **Step 1: Write the tests**

```python
# AlgoCore/tests/test_integration_ml.py
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


def _make_ohlcv(n: int = 60) -> pd.DataFrame:
    np.random.seed(1)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = 3000.0
    rows = []
    for i in range(n):
        price = price * (1 + np.random.uniform(-0.003, 0.003))
        rows.append({
            "timestamp": (base + timedelta(minutes=15 * i)).isoformat(),
            "open": price * 0.999, "high": price * 1.002,
            "low": price * 0.998, "close": price,
            "volume": float(np.random.randint(800, 2000)),
        })
    return pd.DataFrame(rows)


def test_all_phase2_modules_import():
    from services.ml.data.fetcher import OHLCVFetcher
    from services.ml.features import build_features, FEATURE_COLS
    from services.ml.models.xgboost_model import XGBoostModel
    from services.ml.models.ensemble import EnsembleModel
    from services.ml.tracking.mlflow_tracker import MLflowTracker
    from services.ml.training.pipeline import TrainingPipeline
    from services.ml.inference.predictor import Predictor
    from services.ml.service import MLService
    from services.orchestrator.rules import apply_rules
    from services.orchestrator.agent import OrchestratorAgent
    from services.orchestrator.service import OrchestratorService
    from services.notifications.telegram import TelegramClient
    from services.notifications.alerts import AlertSubscriber
    assert True


def test_feature_to_xgboost_signal_flow():
    from services.ml.features import build_features
    from services.ml.models.xgboost_model import XGBoostModel
    from services.ml.inference.predictor import Predictor

    df  = build_features(_make_ohlcv(60))
    assert len(df) > 10, "Not enough rows after feature engineering"
    model = XGBoostModel()
    model.fit(df)
    features = df.drop(columns=["target"]).iloc[-1:]
    pred = Predictor(model)
    action, conf = pred.predict_from_df(features)
    assert action in {"BUY", "SELL", "HOLD"}
    assert 0.0 <= conf <= 1.0


def test_orchestrator_rules_stop_all_flow():
    from services.orchestrator.rules import apply_rules
    risk = {"drawdown_pct": 7.5, "is_stopped": True, "exposure_pct": 80.0}
    decision = apply_rules(risk, [])
    assert decision["action"] == "STOP_ALL"
    assert decision["confidence"] >= 0.9


def test_ml_service_run_once_publishes_signal():
    raw = _make_ohlcv(60)
    mock_model = MagicMock()
    mock_model.is_trained = True
    mock_model.predict.return_value = 0.80

    with patch("services.ml.service.OHLCVFetcher") as MockFetcher, \
         patch("services.ml.service.XGBoostModel", return_value=mock_model), \
         patch("services.ml.service.publish") as mock_pub:
        MockFetcher.return_value.get_candles.return_value = raw
        from services.ml.service import MLService
        svc = MLService("BTCUSDT", "binance", model_path=None)
        svc._run_once()

    mock_pub.assert_called_once()
    channel, payload = mock_pub.call_args[0]
    assert channel == "ml:signal"
    assert payload["symbol"] == "BTCUSDT"
    assert payload["action"] == "BUY"
```

- [ ] **Step 2: Run**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/test_integration_ml.py -v
```
Expected: 4 passed

- [ ] **Step 3: Run full suite to confirm no regressions**

```
cd H:\Dev-Drive && python -m pytest AlgoCore/tests/ -v
```
Expected: all tests pass (30 Phase 1 + new Phase 2 tests)

- [ ] **Step 4: Commit**

```
git add AlgoCore/tests/test_integration_ml.py
git commit -m "test: add Phase 2 integration smoke test"
```

---

## Self-Review

**Spec coverage:**
- ✅ ML Service with XGBoost — Tasks 3–7
- ✅ ML → Orchestrator → Executor integration — Task 8 (orchestrator reads ML_SIGNAL, publishes to ORCH_DECISION; executor wiring is Phase 3)
- ✅ LSTM training pipeline — Task 10
- ✅ MLflow tracking — Task 4–6
- ✅ Telegram alerts — Task 9
- ⚠️ Fear & Greed Index feature — spec lists it as an ML input; not included here (requires external API call, deferred to Phase 3 sentiment service)
- ⚠️ News sentiment score — same: deferred
- ⚠️ Multi-TF features (M5, M15, H1, H4) — LSTM uses M15 only; multi-TF deferred to Phase 3

**Placeholder scan:** None found.

**Type consistency:**
- `FEATURE_COLS` defined in `features.py`, imported by `xgboost_model.py`, `lstm_model.py`, `test_features.py` — consistent
- `build_features(df) -> pd.DataFrame` — used identically in Tasks 3, 6, 7, 10, 11
- `predict(df: pd.DataFrame) -> float` — same signature on XGBoostModel, LSTMModel, EnsembleModel
- `OrchestratorDecision` model not used directly in service.py (publishes dict) — intentional to avoid circular import; consistent with Phase 1 pattern (RiskService also publishes dict not model)
