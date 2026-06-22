import logging
from datetime import datetime, timezone

from services.ml.models.rl_model import RLModel
from services.ml.data.fetcher import OHLCVFetcher
from services.ml.features import build_features
from shared.state import publish
from shared import events
from shared.config import settings


_logger = logging.getLogger(__name__)


class RLService:
    """
    RL-based signal inference service.
    Fetches candles, builds features, trains model (if needed), and publishes signals.
    """

    def __init__(
        self,
        symbol: str,
        exchange: str,
        model_path: str | None = None,
        interval: int = 900,
    ):
        """
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            exchange: Exchange name (e.g., "bitget", "binance")
            model_path: Optional path to load a pre-trained model
            interval: Run interval in seconds (default 900 = 15 min)
        """
        self._symbol = symbol
        self._exchange = exchange
        self._interval = interval
        self._model = RLModel()
        self._fetcher = OHLCVFetcher()

        # Load model if path provided
        if model_path:
            self._model.load(model_path)

    def _run_once(self) -> None:
        """
        Fetch 200 candles, build features, train if needed, and publish signal.
        """
        try:
            # Fetch 200 candles at 15m interval
            df = self._fetcher.get_candles(
                self._symbol,
                self._exchange,
                "15m",
                200,
            )

            # Build features
            df = build_features(df)

            # Train if not yet trained
            if not self._model.is_trained:
                _logger.info(f"Training RLModel for {self._symbol}")
                self._model.fit(df, episodes=20)

            # Predict on latest features (without target column)
            action, confidence = self._model.predict(df)

            # Publish signal
            timestamp = datetime.now(tz=timezone.utc).isoformat()
            payload = {
                "symbol": self._symbol,
                "action": action,
                "confidence": confidence,
                "strategy": "rl",
                "timestamp": timestamp,
            }
            publish(events.ML_SIGNAL, payload)
            _logger.info(f"Published ML_SIGNAL: {payload}")

        except Exception as e:
            _logger.error(f"RLService error: {e}", exc_info=True)

    def run(self) -> None:
        """
        Main execution loop (placeholder for async scheduler integration).
        Currently just calls _run_once(); extend for continuous execution.
        """
        self._run_once()
