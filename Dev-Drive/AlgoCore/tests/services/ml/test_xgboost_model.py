import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta


def _make_feature_df(n: int = 80) -> pd.DataFrame:
    np.random.seed(42)
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


def test_xgboost_save_load():
    import tempfile, os
    from services.ml.models.xgboost_model import XGBoostModel
    model = XGBoostModel()
    model.fit(_make_feature_df(80))
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        model.save(path)
        m2 = XGBoostModel()
        m2.load(path)
        assert m2.is_trained
    finally:
        os.unlink(path)
