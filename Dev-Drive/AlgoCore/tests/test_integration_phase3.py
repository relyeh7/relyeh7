import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock


def _make_ohlcv(n: int = 80) -> pd.DataFrame:
    np.random.seed(3)
    from datetime import datetime, timezone, timedelta
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


def test_all_phase3_modules_import():
    from shared.models import SentimentState
    from shared.events import SENTIMENT_UPDATE
    from services.sentiment.fetcher import SentimentFetcher
    from services.sentiment.service import SentimentService
    from services.ml.models.rl_model import RLModel
    from services.ml.rl_service import RLService
    from services.execution_bridge.bridge import ExecutionBridge
    assert True


def test_rl_feature_to_predict_flow():
    from services.ml.features import build_features
    from services.ml.models.rl_model import RLModel

    df    = build_features(_make_ohlcv(80))
    model = RLModel()
    model.fit(df, episodes=3)
    X     = df.drop(columns=["target"])
    action, conf = model.predict(X)
    assert action in {"BUY", "SELL", "HOLD"}
    assert 0.0 <= conf <= 1.0


def test_sentiment_fetcher_parses_fng_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": [{"value": "45", "value_classification": "Fear"}]}
    with patch("services.sentiment.fetcher.requests.get", return_value=resp):
        from services.sentiment.fetcher import SentimentFetcher
        state = SentimentFetcher(api_key="").fetch()
    assert abs(state.fear_greed_score - 0.45) < 0.01
    assert state.news_sentiment == 0.5


def test_execution_bridge_buy_to_signal_new():
    decision = {
        "action": "BUY", "confidence": 0.88, "exchange": "binance",
        "strategy": "ml", "capital_pct": 0.05,
        "reason": "integration test", "timestamp": "2026-06-21T10:00:00Z",
    }
    with patch("services.execution_bridge.bridge.publish") as mock_pub:
        from services.execution_bridge.bridge import ExecutionBridge
        bridge = ExecutionBridge("ETHUSDT", "binance")
        bridge._process(decision)
    mock_pub.assert_called_once()
    channel, payload = mock_pub.call_args[0]
    assert channel == "signal:new"
    assert payload["symbol"] == "ETHUSDT"
    assert payload["action"] == "BUY"
    assert payload["confidence"] == 0.88
