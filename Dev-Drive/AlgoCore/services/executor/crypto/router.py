from services.executor.crypto.bitget_client import BitgetClient
from services.executor.crypto.binance_client import BinanceClient


class ExchangeRouter:
    def __init__(
        self,
        bitget_client:  BitgetClient  | None = None,
        binance_client: BinanceClient | None = None,
    ):
        self._bitget  = bitget_client  or BitgetClient()
        self._binance = binance_client or BinanceClient()

    def best_exchange(self, symbol: str, side: str = "buy") -> str:
        """Selecciona exchange con mejor precio para el side dado."""
        try:
            p_bitget  = self._bitget.get_ticker(symbol)
            p_binance = self._binance.get_ticker(symbol)
        except Exception:
            return "bitget"  # fallback

        if side == "buy":
            return "bitget" if p_bitget <= p_binance else "binance"
        return "bitget" if p_bitget >= p_binance else "binance"

    def place_order(self, symbol: str, side: str, price: float, size: float) -> str:
        exchange = self.best_exchange(symbol, side)
        if exchange == "bitget":
            return self._bitget.place_order(symbol, side, price, size)
        return self._binance.place_order(symbol, side, price, size)
