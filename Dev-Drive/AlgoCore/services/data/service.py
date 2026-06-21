import threading
from services.data.feeds.bitget_feed import BitgetFeed
from services.data.feeds.binance_feed import BinanceFeed

BITGET_SYMBOLS  = ["ETHUSDT", "BTCUSDT"]
BINANCE_SYMBOLS = ["BTCUSDT", "BNBUSDT"]


class DataService:
    def run(self) -> None:
        feeds = [
            BitgetFeed(BITGET_SYMBOLS),
            BinanceFeed(BINANCE_SYMBOLS),
        ]
        threads = [
            threading.Thread(target=f.start, daemon=True, name=type(f).__name__)
            for f in feeds
        ]
        for t in threads:
            t.start()
        print("[DataService] Feeds iniciados:", [t.name for t in threads])
        for t in threads:
            t.join()


if __name__ == "__main__":
    DataService().run()
