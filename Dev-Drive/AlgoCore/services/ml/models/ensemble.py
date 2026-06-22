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
        self._xgb    = xgb
        self._lstm   = lstm
        self._w_xgb  = weights[0]
        self._w_lstm = weights[1]

    def predict(self, df: pd.DataFrame) -> float:
        xgb_conf = self._xgb.predict(df.iloc[-1:])
        if not self._lstm.is_trained:
            return xgb_conf
        lstm_conf = self._lstm.predict(df)
        return self._w_xgb * xgb_conf + self._w_lstm * lstm_conf
