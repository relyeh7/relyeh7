import tempfile, os
import pandas as pd
import numpy as np
from services.ml.features import FEATURE_COLS


def _make_feature_df(n: int = 80) -> pd.DataFrame:
    np.random.seed(42)
    data = {col: np.random.randn(n) for col in FEATURE_COLS}
    data["target"] = np.random.randint(0, 2, n)
    return pd.DataFrame(data)


def test_rl_model_not_trained_by_default():
    from services.ml.models.rl_model import RLModel
    m = RLModel()
    assert m.is_trained is False


def test_rl_model_fit_returns_metrics():
    from services.ml.models.rl_model import RLModel
    df = _make_feature_df(80)
    m = RLModel()
    result = m.fit(df, episodes=3)
    assert "avg_reward" in result
    assert "episodes" in result
    assert result["episodes"] == 3
    assert m.is_trained is True


def test_rl_model_predict_returns_valid_action():
    from services.ml.models.rl_model import RLModel
    df = _make_feature_df(80)
    m = RLModel()
    m.fit(df, episodes=3)
    action, conf = m.predict(df)
    assert action in {"BUY", "SELL", "HOLD"}
    assert 0.0 <= conf <= 1.0


def test_rl_model_save_load():
    from services.ml.models.rl_model import RLModel
    df = _make_feature_df(80)
    m = RLModel()
    m.fit(df, episodes=3)
    a1, c1 = m.predict(df)

    tmp = tempfile.NamedTemporaryFile(suffix=".pt", delete=False)
    tmp.close()
    try:
        m.save(tmp.name)
        m2 = RLModel()
        m2.load(tmp.name)
        a2, c2 = m2.predict(df)
        assert a2 == a1
        assert abs(c2 - c1) < 1e-4
    finally:
        os.unlink(tmp.name)


def test_rl_service_run_once_publishes_signal():
    from unittest.mock import patch, MagicMock
    from services.ml.rl_service import RLService

    # Mock RLModel
    mock_model = MagicMock()
    mock_model.is_trained = True
    mock_model.predict.return_value = ("BUY", 0.75)

    # Mock OHLCVFetcher
    mock_df = _make_feature_df(200)
    mock_fetcher = MagicMock()
    mock_fetcher.get_candles.return_value = mock_df

    # Mock build_features to return df with FEATURE_COLS + target
    mock_features_df = mock_df.copy()

    # Mock publish
    mock_publish = MagicMock()

    with patch("services.ml.rl_service.RLModel", return_value=mock_model), \
         patch("services.ml.rl_service.OHLCVFetcher", return_value=mock_fetcher), \
         patch("services.ml.rl_service.build_features", return_value=mock_features_df), \
         patch("services.ml.rl_service.publish", mock_publish):

        service = RLService(symbol="BTCUSDT", exchange="bitget")
        service._run_once()

        # Verify fetcher was called
        mock_fetcher.get_candles.assert_called_once_with("BTCUSDT", "bitget", "15m", 200)

        # Verify model.predict was called
        mock_model.predict.assert_called_once()

        # Verify publish was called with correct payload structure
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "ml:signal"  # channel
        payload = call_args[0][1]
        assert payload["symbol"] == "BTCUSDT"
        assert payload["action"] == "BUY"
        assert payload["confidence"] == 0.75
        assert payload["strategy"] == "rl"
        assert "timestamp" in payload
