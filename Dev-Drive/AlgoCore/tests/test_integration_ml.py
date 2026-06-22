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
