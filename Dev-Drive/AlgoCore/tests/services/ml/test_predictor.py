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
    mock_model.predict.return_value = 0.75
    pred = Predictor(mock_model)
    action, conf = pred.predict_from_df(_make_feature_row())
    assert action == "BUY"
    assert conf == 0.75


def test_predictor_sell_signal():
    from services.ml.inference.predictor import Predictor
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.30
    pred = Predictor(mock_model)
    action, conf = pred.predict_from_df(_make_feature_row())
    assert action == "SELL"
    assert conf == 0.30


def test_predictor_hold_signal():
    from services.ml.inference.predictor import Predictor
    mock_model = MagicMock()
    mock_model.predict.return_value = 0.50
    pred = Predictor(mock_model)
    action, conf = pred.predict_from_df(_make_feature_row())
    assert action == "HOLD"
    assert conf == 0.50


def test_ml_service_publishes_signal():
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
