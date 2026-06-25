from unittest.mock import patch, MagicMock


def test_symbol_router_get_symbols():
    from services.routing.symbol_router import SymbolRouter
    router = SymbolRouter(["BTCUSDT", "ETHUSDT"])
    assert router.get_symbols() == ["BTCUSDT", "ETHUSDT"]


def test_symbol_router_run_once_all_calls_each_symbol():
    from services.routing.symbol_router import SymbolRouter
    mock_svc = MagicMock()
    mock_svc._run_once.return_value = None

    with patch("services.routing.symbol_router.MLService", return_value=mock_svc):
        router = SymbolRouter(["BTCUSDT", "ETHUSDT"], exchange="bitget")
        processed = router.run_once_all()

    assert set(processed) == {"BTCUSDT", "ETHUSDT"}
    assert mock_svc._run_once.call_count == 2


def test_symbol_router_deduplicates_symbols():
    from services.routing.symbol_router import SymbolRouter
    router = SymbolRouter(["BTCUSDT", "BTCUSDT", "ETHUSDT"])
    assert len(router.get_symbols()) == 2
    assert "BTCUSDT" in router.get_symbols()
    assert "ETHUSDT" in router.get_symbols()
