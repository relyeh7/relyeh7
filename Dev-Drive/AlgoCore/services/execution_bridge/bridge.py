import time
import logging
from shared.state import subscribe_once, publish
from shared import events
from shared.models import Exchange
from shared.config import settings

logger = logging.getLogger(__name__)


class ExecutionBridge:
    """
    Polls orchestrator decisions and publishes active actions to the execution layer.
    Maps exchange names and filters to only publish BUY, SELL, and STOP_ALL actions.
    """

    def __init__(self, symbol: str, exchange: str, poll_interval: int = 5):
        """
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            exchange: Exchange name (e.g., "auto", "bitget", "binance", "mt5")
            poll_interval: Seconds between polls (default 5)
        """
        self.symbol = symbol
        self.exchange = self._map_exchange(exchange)
        self.poll_interval = poll_interval
        self._last_id = "0"

    @staticmethod
    def _map_exchange(exchange: str) -> str:
        """Map exchange name to standard Exchange enum value."""
        mapping = {
            "auto": Exchange.BITGET.value,
            "bitget": Exchange.BITGET.value,
            "binance": Exchange.BINANCE.value,
            "mt5": Exchange.MT5.value,
        }
        return mapping.get(exchange, Exchange.BITGET.value)

    def _process(self, decision: dict) -> bool:
        """
        Process a single orchestrator decision.
        Only publishes BUY, SELL, and STOP_ALL actions.
        Maps STOP_ALL to CANCEL_ALL in the output.

        Returns:
            True if the decision was published, False otherwise.
        """
        action = decision.get("action", "HOLD").upper()

        # Only publish active actions
        if action not in ("BUY", "SELL", "STOP_ALL"):
            return False

        # Map STOP_ALL to CANCEL_ALL for the execution layer
        out_action = "CANCEL_ALL" if action == "STOP_ALL" else action

        # Map decision's exchange to standard value
        decision_exchange = decision.get("exchange", "auto")
        output_exchange = self._map_exchange(decision_exchange)

        # Build the execution payload
        payload = {
            "symbol": self.symbol,
            "action": out_action,
            "confidence": decision.get("confidence", 0.5),
            "strategy": decision.get("strategy", "ml"),
            "exchange": output_exchange,
            "timestamp": decision.get("timestamp"),
        }

        # Publish to the execution layer
        try:
            publish(events.SIGNAL_NEW, payload)
            logger.debug(f"Published execution decision: {payload}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish execution decision: {e}")
            return False

    def run(self):
        """
        Poll orchestrator decisions indefinitely and process them.
        Blocks with subscribe_once every poll_interval seconds.
        """
        logger.info(
            f"ExecutionBridge started for {self.symbol} on {self.exchange} "
            f"(poll_interval={self.poll_interval}s)"
        )

        while True:
            try:
                # Poll for new orchestrator decisions
                decisions = subscribe_once(
                    events.ORCH_DECISION, last_id=self._last_id
                )

                # Process each decision
                for decision in decisions:
                    self._process(decision)

                # Update last ID for next poll
                if decisions:
                    self._last_id = decisions[-1].get("timestamp", self._last_id)

                # Sleep before next poll
                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("ExecutionBridge interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in ExecutionBridge.run(): {e}")
                time.sleep(self.poll_interval)


if __name__ == "__main__":
    ExecutionBridge(settings.trading_symbol, "auto").run()
