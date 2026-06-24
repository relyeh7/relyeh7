import threading
import logging
from shared.config import settings
from services.data.feeds.bitget_feed import BitgetFeed
from services.data.feeds.binance_feed import BinanceFeed
from services.data.feeds.rest_poller import RestPriceFeed
from services.executor.crypto.router import ExchangeRouter

logger = logging.getLogger(__name__)


class DataService:
    def run(self) -> None:
        symbols = settings.trading_symbols
        router  = ExchangeRouter()

        feeds = [
            BitgetFeed(symbols),
            BinanceFeed(symbols),
            RestPriceFeed(router=router, symbols=symbols, poll_sec=settings.feed_poll_sec),
        ]
        threads = [
            threading.Thread(target=f.start if hasattr(f, "start") else f.run,
                             daemon=True, name=type(f).__name__)
            for f in feeds
        ]
        for t in threads:
            t.start()
        logger.info("[DataService] Feeds iniciados: %s", [t.name for t in threads])
        print("[DataService] Feeds iniciados:", [t.name for t in threads])
        for t in threads:
            t.join()


if __name__ == "__main__":
    DataService().run()
