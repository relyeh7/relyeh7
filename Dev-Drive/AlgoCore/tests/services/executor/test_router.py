import pytest
from unittest.mock import MagicMock


def test_router_selects_bitget_for_eth():
    from services.executor.crypto.router import ExchangeRouter
    bitget  = MagicMock(); bitget.get_ticker.return_value  = 2500.0
    binance = MagicMock(); binance.get_ticker.return_value = 2501.0
    router  = ExchangeRouter(bitget_client=bitget, binance_client=binance)
    # Bitget tiene precio más bajo → mejor para comprar
    exchange = router.best_exchange("ETHUSDT", side="buy")
    assert exchange == "bitget"


def test_router_place_order_delegates_to_correct_client():
    from services.executor.crypto.router import ExchangeRouter
    bitget  = MagicMock(); bitget.get_ticker.return_value  = 2500.0
    binance = MagicMock(); binance.get_ticker.return_value = 2501.0
    bitget.place_order.return_value = "bg-order-1"
    router  = ExchangeRouter(bitget_client=bitget, binance_client=binance)
    oid = router.place_order("ETHUSDT", "buy", 2500.0, 0.01)
    assert oid == "bg-order-1"
    bitget.place_order.assert_called_once_with("ETHUSDT", "buy", 2500.0, 0.01)
