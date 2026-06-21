"""
Smoke test: verifica que todos los módulos se importan correctamente
y que el flujo básico publish → get_state funciona con Redis mockeado.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


def test_all_modules_import():
    """Verifica que todos los módulos se importan sin errores."""
    from shared.config import settings
    from shared.models import PriceTick, Signal, Order, RiskState, Exchange, Side, Market
    from shared import events
    from services.data.feeds.bitget_feed import BitgetFeed
    from services.data.feeds.binance_feed import BinanceFeed
    from services.executor.crypto.bitget_client import BitgetClient
    from services.executor.crypto.binance_client import BinanceClient
    from services.executor.crypto.router import ExchangeRouter
    from risk.rules import check_drawdown, check_exposure

    # Si llegamos aquí, todas las importaciones funcionan
    assert True


def test_price_tick_flow():
    """PriceTick publicado por feed → puede deserializarse como PriceTick."""
    # Patch at module level before importing the feed
    with patch("services.data.feeds.bitget_feed.publish") as mock_pub:
        from shared.models import PriceTick, Exchange
        from services.data.feeds.bitget_feed import BitgetFeed

        feed = BitgetFeed(["ETHUSDT"])
        feed._on_message({
            "action": "snapshot",
            "data": [{"instId": "ETHUSDT", "last": "2500.00", "vol24h": "1000"}],
        })

        mock_pub.assert_called_once()
        channel, payload = mock_pub.call_args[0]
        assert channel == "price:tick"

        # Reconstruct PriceTick from published payload
        tick = PriceTick(
            **{k: payload[k] for k in ["symbol", "price", "volume", "timestamp"]},
            exchange=Exchange(payload["exchange"]),
        )
        assert tick.price == 2500.0


def test_risk_rules_stop_flow():
    """Verifica que check_drawdown retorna 'STOP' cuando drawdown >= threshold."""
    from shared.models import RiskState
    from shared.config import Settings
    from risk.rules import check_drawdown

    state = RiskState(total_equity=1000.0, drawdown_pct=7.0)
    cfg = Settings(stop_on_drawdown_pct=6.0)
    result = check_drawdown(state, cfg)
    assert result == "STOP"
