import pandas as pd
from services.ml.models.xgboost_model import XGBoostModel


class Predictor:
    BUY_THRESHOLD  = 0.6
    SELL_THRESHOLD = 0.4

    def __init__(self, model: XGBoostModel):
        self._model = model

    def predict_from_df(self, df: pd.DataFrame) -> tuple[str, float]:
        conf = self._model.predict(df)
        if conf > self.BUY_THRESHOLD:
            return "BUY", conf
        if conf < self.SELL_THRESHOLD:
            return "SELL", conf
        return "HOLD", conf
