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
    mock_tracker.start_run.return_value = "run-abc"

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
    mock_tracker.start_run.return_value = "run-xyz"

    with patch("services.ml.training.pipeline.build_features", return_value=_make_feature_df()):
        from services.ml.training.pipeline import TrainingPipeline
        pipeline = TrainingPipeline("ETHUSDT", "bitget", mock_tracker,
                                    fetcher=mock_fetcher, model=mock_model)
        result = pipeline.run(min_sharpe=1.0)
    assert result is False
    mock_tracker.register_model.assert_not_called()
