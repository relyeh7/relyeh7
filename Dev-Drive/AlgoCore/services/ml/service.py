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


if __name__ == "__main__":
    from shared.config import settings

    MLService(settings.trading_symbol, "binance").run()
