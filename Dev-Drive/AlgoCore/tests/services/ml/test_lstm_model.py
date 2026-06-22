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
