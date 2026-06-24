from threading import Thread

from services.ml.service import MLService


class SymbolRouter:
    def __init__(self, symbols: list[str], exchange: str = "bitget"):
        seen: set[str] = set()
        self._symbols: list[str] = []
        for s in symbols:
            if s not in seen:
                seen.add(s)
                self._symbols.append(s)
        self._exchange = exchange

    def get_symbols(self) -> list[str]:
        return list(self._symbols)

    def run_once_all(self) -> list[str]:
        processed = []
        for symbol in self._symbols:
            svc = MLService(symbol, self._exchange)
            svc._run_once()
            processed.append(symbol)
        return processed

    def run(self) -> None:
        threads = [
            Thread(
                target=MLService(symbol, self._exchange).run,
                name=f"ml-{symbol}",
                daemon=True,
            )
            for symbol in self._symbols
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()


if __name__ == "__main__":
    from shared.config import settings
    SymbolRouter(settings.trading_symbols).run()
