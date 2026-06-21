# AlgoCore Phase 1 — Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levantar la infraestructura base de AlgoCore: Message Bus, feeds de precio en tiempo real (Bitget + Binance), ejecutor crypto básico, risk service con reglas de drawdown, y dashboard mínimo con P&L en tiempo real.

**Architecture:** 7 servicios independientes comunicados via Redis Streams. Cada servicio es un proceso Python separado. Docker Compose levanta todo con un comando. Los servicios se descubren entre sí via Redis, no via red directa.

**Tech Stack:** Python 3.11, Redis 7 (Streams), PostgreSQL 15, FastAPI 0.111, pydantic-settings 2, websockets 12, python-bitget, python-binance, pytest, Docker Compose v2

## Global Constraints

- Python 3.11+ (usa `X | Y` type unions, `match` statements)
- Pydantic v2 (usa `model_validate`, no `parse_obj`)
- Todos los secretos desde `.env` via `pydantic-settings` — nunca hardcodeados
- Redis Streams para mensajes async; Redis Hash/String para estado actual
- Cada servicio tiene su propio `requirements.txt` + `Dockerfile`
- Tests con `pytest` — fixtures en `conftest.py`, mocks para APIs externas
- Commits en inglés con prefijo convencional (`feat:`, `test:`, `fix:`, `chore:`)
- Directorio raíz: `H:\Dev-Drive\AlgoCore\`

---

## File Map

```
AlgoCore/
├── shared/
│   ├── __init__.py
│   ├── config.py          # pydantic-settings: todas las env vars
│   ├── models.py          # Pydantic schemas: PriceTick, Signal, Order, RiskState
│   ├── events.py          # Constantes de canales Redis
│   └── state.py           # publish/subscribe/get_state/set_state sobre Redis
├── services/
│   ├── data/
│   │   ├── __init__.py
│   │   ├── feeds/
│   │   │   ├── __init__.py
│   │   │   ├── bitget_feed.py   # WebSocket Bitget → publica PriceTick en Redis
│   │   │   └── binance_feed.py  # WebSocket Binance → publica PriceTick en Redis
│   │   └── service.py           # Lanza ambos feeds en threads, maneja reconexión
│   ├── executor/
│   │   └── crypto/
│   │       ├── __init__.py
│   │       ├── bitget_client.py  # REST: place_order, cancel, get_balance
│   │       ├── binance_client.py # REST: place_order, cancel, get_balance
│   │       ├── router.py         # Elige exchange por fee/liquidez
│   │       └── service.py        # Escucha señales Redis → ejecuta órdenes
│   └── dashboard/
│       └── api/
│           ├── __init__.py
│           ├── main.py           # FastAPI app + WebSocket endpoint
│           └── routes/
│               ├── __init__.py
│               ├── status.py     # GET /status → estado de todos los servicios
│               └── pnl.py        # GET /pnl → P&L total y por estrategia
├── risk/
│   ├── __init__.py
│   ├── rules.py           # Funciones puras: check_drawdown, check_exposure
│   └── service.py         # Loop: lee RiskState de Redis, aplica reglas, publica alertas
├── tests/
│   ├── conftest.py        # Fixtures: fake_redis, mock_bitget, mock_binance
│   ├── shared/
│   │   ├── test_models.py
│   │   └── test_state.py
│   ├── services/
│   │   ├── data/
│   │   │   └── test_feeds.py
│   │   └── executor/
│   │       ├── test_bitget_client.py
│   │       ├── test_binance_client.py
│   │       └── test_router.py
│   └── risk/
│       └── test_rules.py
├── docker-compose.yml
├── .env.example
├── pyproject.toml
└── requirements.txt
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `AlgoCore/pyproject.toml`
- Create: `AlgoCore/requirements.txt`
- Create: `AlgoCore/.env.example`
- Create: `AlgoCore/docker-compose.yml`
- Create: `AlgoCore/shared/__init__.py` (vacío)
- Create: `AlgoCore/services/data/feeds/__init__.py` (vacío)
- Create: `AlgoCore/services/executor/crypto/__init__.py` (vacío)
- Create: `AlgoCore/services/dashboard/api/routes/__init__.py` (vacío)
- Create: `AlgoCore/risk/__init__.py` (vacío)
- Create: `AlgoCore/tests/conftest.py`

**Interfaces:**
- Produce: estructura de carpetas + Docker Compose con Redis y PostgreSQL listos

- [ ] **Step 1: Crear directorio raíz**

```bash
cd H:\Dev-Drive
mkdir AlgoCore
cd AlgoCore
git init
```

- [ ] **Step 2: Crear pyproject.toml**

```toml
# AlgoCore/pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "algocore"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.setuptools.packages.find]
where = ["."]
```

- [ ] **Step 3: Crear requirements.txt**

```text
# AlgoCore/requirements.txt
pydantic==2.7.1
pydantic-settings==2.2.1
redis==5.0.4
fastapi==0.111.0
uvicorn[standard]==0.29.0
websockets==12.0
httpx==0.27.0
python-dotenv==1.0.1
pybitget==1.0.6
python-binance==1.0.19
pytest==8.2.0
pytest-asyncio==0.23.6
pytest-mock==3.14.0
```

- [ ] **Step 4: Crear .env.example**

```bash
# AlgoCore/.env.example
# Bitget
BITGET_API_KEY=
BITGET_API_SECRET=
BITGET_API_PASSPHRASE=

# Binance
BINANCE_API_KEY=
BINANCE_API_SECRET=

# LLM
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Infraestructura
REDIS_URL=redis://localhost:6379
POSTGRES_URL=postgresql://algocore:algocore@localhost:5432/algocore

# Risk
MAX_DAILY_DRAWDOWN_PCT=6.0
STOP_ON_DRAWDOWN_PCT=6.0
MAX_EXPOSURE_PCT=90.0
```

- [ ] **Step 5: Crear docker-compose.yml**

```yaml
# AlgoCore/docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: algocore
      POSTGRES_PASSWORD: algocore
      POSTGRES_DB: algocore
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data

volumes:
  redis_data:
  pg_data:
```

- [ ] **Step 6: Crear conftest.py de tests**

```python
# AlgoCore/tests/conftest.py
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_redis():
    with patch("shared.state._redis") as mock:
        mock.xadd = MagicMock()
        mock.xread = MagicMock(return_value=[])
        mock.set = MagicMock()
        mock.get = MagicMock(return_value=None)
        yield mock


@pytest.fixture
def mock_bitget_client():
    client = MagicMock()
    client.get_ticker.return_value = {"lastPr": "2500.00", "vol": "1000.0"}
    client.place_order.return_value = {"orderId": "test-order-123"}
    client.get_account_balance.return_value = [
        {"coin": "USDT", "available": "500.0"},
        {"coin": "ETH", "available": "0.1"},
    ]
    return client


@pytest.fixture
def mock_binance_client():
    client = MagicMock()
    client.get_symbol_ticker.return_value = {"price": "65000.00"}
    client.order_limit_buy.return_value = {"orderId": 987654321}
    client.get_asset_balance.return_value = {"free": "500.0", "locked": "0.0"}
    return client
```

- [ ] **Step 7: Crear directorios con __init__.py vacíos**

```bash
# Ejecutar desde AlgoCore/
mkdir -p shared services/data/feeds services/executor/crypto
mkdir -p services/dashboard/api/routes risk
mkdir -p tests/shared tests/services/data tests/services/executor tests/risk
touch shared/__init__.py services/__init__.py
touch services/data/__init__.py services/data/feeds/__init__.py
touch services/executor/__init__.py services/executor/crypto/__init__.py
touch services/dashboard/__init__.py services/dashboard/api/__init__.py
touch services/dashboard/api/routes/__init__.py
touch risk/__init__.py
touch tests/__init__.py tests/shared/__init__.py
touch tests/services/__init__.py tests/services/data/__init__.py
touch tests/services/executor/__init__.py tests/risk/__init__.py
```

- [ ] **Step 8: Verificar estructura**

```bash
python -m pytest tests/ --collect-only
```
Expected: "no tests ran" (sin error de importación)

- [ ] **Step 9: Commit**

```bash
git add .
git commit -m "chore: scaffold AlgoCore project structure"
```

---

## Task 2: Shared Config + Models + Events

**Files:**
- Create: `shared/config.py`
- Create: `shared/models.py`
- Create: `shared/events.py`
- Create: `tests/shared/test_models.py`

**Interfaces:**
- Produce:
  - `Settings` (pydantic-settings) — importar con `from shared.config import settings`
  - `PriceTick`, `Signal`, `Order`, `RiskState` — importar desde `shared.models`
  - Constantes de canal Redis — importar desde `shared.events`

- [ ] **Step 1: Escribir tests de modelos**

```python
# tests/shared/test_models.py
from datetime import datetime, timezone
from shared.models import PriceTick, Signal, Order, RiskState, Exchange, Side


def test_price_tick_validation():
    tick = PriceTick(
        symbol="ETHUSDT",
        price=2500.0,
        volume=1000.0,
        timestamp=datetime.now(timezone.utc),
        exchange=Exchange.BITGET,
    )
    assert tick.price == 2500.0
    assert tick.exchange == Exchange.BITGET


def test_signal_action_must_be_valid():
    sig = Signal(
        symbol="BTCUSDT",
        action="BUY",
        confidence=0.85,
        strategy="ml_xgboost",
        exchange=Exchange.BINANCE,
        timestamp=datetime.now(timezone.utc),
    )
    assert sig.confidence == 0.85


def test_risk_state_defaults():
    state = RiskState(total_equity=1000.0)
    assert state.daily_pnl == 0.0
    assert state.is_stopped is False
    assert state.drawdown_pct == 0.0


def test_order_roundtrip():
    order = Order(
        order_id="abc-123",
        symbol="ETHUSDT",
        side=Side.BUY,
        price=2490.0,
        size=0.01,
        exchange=Exchange.BITGET,
        status="open",
        timestamp=datetime.now(timezone.utc),
    )
    dumped = order.model_dump()
    restored = Order.model_validate(dumped)
    assert restored.order_id == "abc-123"
```

- [ ] **Step 2: Verificar que el test falla**

```bash
python -m pytest tests/shared/test_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'shared'`

- [ ] **Step 3: Crear shared/events.py**

```python
# shared/events.py

# Redis Stream channels
PRICE_TICK    = "price:tick"
SIGNAL_NEW    = "signal:new"
ORDER_PLACED  = "order:placed"
ORDER_FILLED  = "order:filled"
RISK_UPDATE   = "risk:update"
RISK_ALERT    = "risk:alert"
ORCH_DECISION = "orchestrator:decision"

# Redis Hash keys (estado actual)
STATE_RISK    = "state:risk"
STATE_PRICES  = "state:prices"
STATE_ORDERS  = "state:orders:active"
```

- [ ] **Step 4: Crear shared/models.py**

```python
# shared/models.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Exchange(str, Enum):
    BITGET  = "bitget"
    BINANCE = "binance"
    MT5     = "mt5"


class Market(str, Enum):
    CRYPTO = "crypto"
    FOREX  = "forex"


class Side(str, Enum):
    BUY  = "buy"
    SELL = "sell"


class PriceTick(BaseModel):
    symbol:    str
    price:     float
    volume:    float
    timestamp: datetime
    exchange:  Exchange


class Signal(BaseModel):
    symbol:     str
    action:     str          # BUY | SELL | HOLD
    confidence: float = Field(ge=0.0, le=1.0)
    strategy:   str
    exchange:   Exchange
    timestamp:  datetime


class Order(BaseModel):
    order_id:  str
    symbol:    str
    side:      Side
    price:     float
    size:      float
    exchange:  Exchange
    status:    str           # open | filled | cancelled
    timestamp: datetime


class RiskState(BaseModel):
    total_equity:   float
    daily_pnl:      float = 0.0
    daily_pnl_pct:  float = 0.0
    drawdown_pct:   float = 0.0
    exposure_pct:   float = 0.0
    is_stopped:     bool  = False
    open_positions: int   = 0
```

- [ ] **Step 5: Crear shared/config.py**

```python
# shared/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Bitget
    bitget_api_key:        str   = ""
    bitget_api_secret:     str   = ""
    bitget_api_passphrase: str   = ""

    # Binance
    binance_api_key:    str = ""
    binance_api_secret: str = ""

    # LLM
    anthropic_api_key: str = ""
    gemini_api_key:    str = ""

    # Infraestructura
    redis_url:    str = "redis://localhost:6379"
    postgres_url: str = "postgresql://algocore:algocore@localhost:5432/algocore"

    # Risk thresholds
    max_daily_drawdown_pct: float = 6.0
    stop_on_drawdown_pct:   float = 6.0
    max_exposure_pct:       float = 90.0


settings = Settings()
```

- [ ] **Step 6: Ejecutar tests**

```bash
python -m pytest tests/shared/test_models.py -v
```
Expected: 4 tests PASSED

- [ ] **Step 7: Commit**

```bash
git add shared/ tests/shared/test_models.py
git commit -m "feat: add shared config, models and events"
```

---

## Task 3: Redis State Manager

**Files:**
- Create: `shared/state.py`
- Create: `tests/shared/test_state.py`

**Interfaces:**
- Consumes: `shared.config.settings.redis_url`
- Produce:
  - `publish(channel: str, data: dict) -> None`
  - `get_state(key: str) -> dict | None`
  - `set_state(key: str, data: dict) -> None`
  - `subscribe_once(channel: str, last_id: str) -> list[dict]` — lee mensajes nuevos sin bloquear

- [ ] **Step 1: Escribir tests**

```python
# tests/shared/test_state.py
import json
import pytest
from unittest.mock import MagicMock, patch, call


@pytest.fixture(autouse=True)
def patch_redis():
    with patch("shared.state._redis") as mock:
        yield mock


def test_publish_adds_to_stream(patch_redis):
    from shared.state import publish
    publish("price:tick", {"price": 2500.0})
    patch_redis.xadd.assert_called_once()
    args = patch_redis.xadd.call_args
    assert args[0][0] == "price:tick"
    payload = json.loads(args[0][1]["payload"])
    assert payload["price"] == 2500.0


def test_set_state_stores_json(patch_redis):
    from shared.state import set_state
    set_state("risk", {"drawdown": 1.5})
    patch_redis.set.assert_called_once_with(
        "state:risk", json.dumps({"drawdown": 1.5})
    )


def test_get_state_returns_none_when_missing(patch_redis):
    from shared.state import get_state
    patch_redis.get.return_value = None
    result = get_state("nonexistent")
    assert result is None


def test_get_state_deserializes_json(patch_redis):
    from shared.state import get_state
    patch_redis.get.return_value = json.dumps({"equity": 1000.0})
    result = get_state("risk")
    assert result["equity"] == 1000.0


def test_subscribe_once_returns_payloads(patch_redis):
    from shared.state import subscribe_once
    payload = json.dumps({"price": 2500.0})
    patch_redis.xread.return_value = [
        ("price:tick", [("1-0", {"payload": payload})])
    ]
    results = subscribe_once("price:tick", "$")
    assert len(results) == 1
    assert results[0]["price"] == 2500.0
```

- [ ] **Step 2: Verificar que fallan**

```bash
python -m pytest tests/shared/test_state.py -v
```
Expected: `ModuleNotFoundError` o `ImportError`

- [ ] **Step 3: Implementar shared/state.py**

```python
# shared/state.py
import json
import redis as redis_lib
from shared.config import settings

_redis = redis_lib.from_url(settings.redis_url, decode_responses=True)


def publish(channel: str, data: dict) -> None:
    _redis.xadd(channel, {"payload": json.dumps(data, default=str)})


def set_state(key: str, data: dict) -> None:
    _redis.set(f"state:{key}", json.dumps(data, default=str))


def get_state(key: str) -> dict | None:
    val = _redis.get(f"state:{key}")
    return json.loads(val) if val else None


def subscribe_once(channel: str, last_id: str = "$") -> list[dict]:
    """Lee hasta 20 mensajes nuevos del stream sin bloquear (timeout=100ms)."""
    msgs = _redis.xread({channel: last_id}, block=100, count=20) or []
    result = []
    for _stream, messages in msgs:
        for _msg_id, fields in messages:
            result.append(json.loads(fields["payload"]))
    return result
```

- [ ] **Step 4: Ejecutar tests**

```bash
python -m pytest tests/shared/test_state.py -v
```
Expected: 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add shared/state.py tests/shared/test_state.py
git commit -m "feat: add Redis state manager with publish/subscribe"
```

---

## Task 4: Data Service — Price Feeds

**Files:**
- Create: `services/data/feeds/bitget_feed.py`
- Create: `services/data/feeds/binance_feed.py`
- Create: `services/data/service.py`
- Create: `tests/services/data/test_feeds.py`

**Interfaces:**
- Consumes: `shared.state.publish`, `shared.events.PRICE_TICK`, `shared.models.PriceTick`, `shared.config.settings`
- Produce:
  - `BitgetFeed(symbols: list[str]).start() -> None` — loop WebSocket, publica en Redis
  - `BinanceFeed(symbols: list[str]).start() -> None` — loop WebSocket, publica en Redis
  - `DataService().run() -> None` — lanza ambos feeds en threads con reconexión

- [ ] **Step 1: Escribir tests**

```python
# tests/services/data/test_feeds.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone


def test_bitget_feed_publishes_price_tick():
    with patch("shared.state.publish") as mock_publish:
        from services.data.feeds.bitget_feed import BitgetFeed

        feed = BitgetFeed(symbols=["ETHUSDT"])
        # Simular un mensaje WebSocket recibido
        raw_msg = {
            "action": "snapshot",
            "data": [{"instId": "ETHUSDT", "last": "2500.00", "vol24h": "10000"}],
        }
        feed._on_message(raw_msg)

        mock_publish.assert_called_once()
        channel, payload = mock_publish.call_args[0]
        assert channel == "price:tick"
        assert payload["symbol"] == "ETHUSDT"
        assert payload["price"] == 2500.0
        assert payload["exchange"] == "bitget"


def test_binance_feed_publishes_price_tick():
    with patch("shared.state.publish") as mock_publish:
        from services.data.feeds.binance_feed import BinanceFeed

        feed = BinanceFeed(symbols=["BTCUSDT"])
        raw_msg = {
            "s": "BTCUSDT",
            "c": "65000.00",
            "v": "500.0",
            "T": 1718900000000,
        }
        feed._on_message(raw_msg)

        mock_publish.assert_called_once()
        channel, payload = mock_publish.call_args[0]
        assert channel == "price:tick"
        assert payload["symbol"] == "BTCUSDT"
        assert payload["price"] == 65000.0
        assert payload["exchange"] == "binance"


def test_bitget_feed_ignores_malformed_message():
    with patch("shared.state.publish") as mock_publish:
        from services.data.feeds.bitget_feed import BitgetFeed

        feed = BitgetFeed(symbols=["ETHUSDT"])
        feed._on_message({"unexpected": "format"})
        mock_publish.assert_not_called()
```

- [ ] **Step 2: Verificar que fallan**

```bash
python -m pytest tests/services/data/test_feeds.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Crear services/data/feeds/bitget_feed.py**

```python
# services/data/feeds/bitget_feed.py
import json
import time
import threading
import websocket
from datetime import datetime, timezone
from shared import events
from shared.state import publish
from shared.config import settings


class BitgetFeed:
    WS_URL = "wss://ws.bitget.com/v2/ws/public"

    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self._ws = None

    def _on_message(self, msg: dict) -> None:
        data = msg.get("data")
        if not data or not isinstance(data, list):
            return
        for item in data:
            try:
                publish(events.PRICE_TICK, {
                    "symbol":    item["instId"],
                    "price":     float(item["last"]),
                    "volume":    float(item.get("vol24h", 0)),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "exchange":  "bitget",
                })
            except (KeyError, ValueError):
                pass

    def _on_raw(self, ws, raw):
        try:
            msg = json.loads(raw)
            self._on_message(msg)
        except json.JSONDecodeError:
            pass

    def start(self) -> None:
        """Conecta WebSocket y escucha indefinidamente con reconexión."""
        subs = [{"instType": "SPOT", "channel": "ticker", "instId": s}
                for s in self.symbols]
        while True:
            try:
                ws = websocket.WebSocketApp(
                    self.WS_URL,
                    on_open=lambda ws: ws.send(json.dumps({"op": "subscribe", "args": subs})),
                    on_message=self._on_raw,
                )
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print(f"[BitgetFeed] Error: {e} — reconectando en 5s")
            time.sleep(5)
```

- [ ] **Step 4: Crear services/data/feeds/binance_feed.py**

```python
# services/data/feeds/binance_feed.py
import json
import time
import websocket
from datetime import datetime, timezone
from shared import events
from shared.state import publish


class BinanceFeed:
    WS_BASE = "wss://stream.binance.com:9443/stream?streams="

    def __init__(self, symbols: list[str]):
        self.symbols = symbols

    def _on_message(self, msg: dict) -> None:
        try:
            publish(events.PRICE_TICK, {
                "symbol":    msg["s"],
                "price":     float(msg["c"]),
                "volume":    float(msg["v"]),
                "timestamp": datetime.fromtimestamp(
                    msg["T"] / 1000, tz=timezone.utc
                ).isoformat(),
                "exchange":  "binance",
            })
        except (KeyError, ValueError):
            pass

    def _on_raw(self, ws, raw):
        try:
            outer = json.loads(raw)
            self._on_message(outer.get("data", outer))
        except json.JSONDecodeError:
            pass

    def start(self) -> None:
        streams = "/".join(f"{s.lower()}@miniTicker" for s in self.symbols)
        url = self.WS_BASE + streams
        while True:
            try:
                ws = websocket.WebSocketApp(url, on_message=self._on_raw)
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                print(f"[BinanceFeed] Error: {e} — reconectando en 5s")
            time.sleep(5)
```

- [ ] **Step 5: Crear services/data/service.py**

```python
# services/data/service.py
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
```

- [ ] **Step 6: Ejecutar tests**

```bash
python -m pytest tests/services/data/test_feeds.py -v
```
Expected: 3 tests PASSED

- [ ] **Step 7: Commit**

```bash
git add services/data/ tests/services/data/
git commit -m "feat: add Bitget and Binance WebSocket price feeds"
```

---

## Task 5: Executor Crypto — Bitget Client

**Files:**
- Create: `services/executor/crypto/bitget_client.py`
- Create: `tests/services/executor/test_bitget_client.py`

**Interfaces:**
- Consumes: `shared.config.settings` (bitget_api_key, bitget_api_secret, bitget_api_passphrase)
- Produce:
  - `BitgetClient.get_balance(coin: str) -> float`
  - `BitgetClient.place_order(symbol: str, side: str, price: float, size: float) -> str` — retorna order_id
  - `BitgetClient.cancel_order(symbol: str, order_id: str) -> bool`
  - `BitgetClient.get_ticker(symbol: str) -> float` — retorna último precio

- [ ] **Step 1: Escribir tests**

```python
# tests/services/executor/test_bitget_client.py
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_requests():
    with patch("services.executor.crypto.bitget_client.requests") as m:
        yield m


def _mock_response(mock_requests, json_data: dict):
    resp = MagicMock()
    resp.json.return_value = {"code": "00000", "data": json_data}
    resp.raise_for_status = MagicMock()
    mock_requests.get.return_value = resp
    mock_requests.post.return_value = resp
    return resp


def test_get_ticker_returns_price(mock_requests):
    from services.executor.crypto.bitget_client import BitgetClient
    _mock_response(mock_requests, [{"lastPr": "2500.50"}])
    client = BitgetClient()
    price = client.get_ticker("ETHUSDT")
    assert price == 2500.50


def test_get_balance_returns_available(mock_requests):
    from services.executor.crypto.bitget_client import BitgetClient
    _mock_response(mock_requests, [
        {"coin": "USDT", "available": "500.25"},
        {"coin": "ETH",  "available": "0.1"},
    ])
    client = BitgetClient()
    balance = client.get_balance("USDT")
    assert balance == 500.25


def test_place_order_returns_order_id(mock_requests):
    from services.executor.crypto.bitget_client import BitgetClient
    _mock_response(mock_requests, {"orderId": "bg-order-999"})
    client = BitgetClient()
    order_id = client.place_order("ETHUSDT", "buy", 2490.0, 0.01)
    assert order_id == "bg-order-999"


def test_cancel_order_returns_true(mock_requests):
    from services.executor.crypto.bitget_client import BitgetClient
    _mock_response(mock_requests, {})
    client = BitgetClient()
    result = client.cancel_order("ETHUSDT", "bg-order-999")
    assert result is True
```

- [ ] **Step 2: Verificar que fallan**

```bash
python -m pytest tests/services/executor/test_bitget_client.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Crear services/executor/crypto/bitget_client.py**

```python
# services/executor/crypto/bitget_client.py
import hmac
import hashlib
import base64
import time
import requests
from shared.config import settings


class BitgetClient:
    BASE = "https://api.bitget.com"

    def __init__(self):
        self._key        = settings.bitget_api_key
        self._secret     = settings.bitget_api_secret
        self._passphrase = settings.bitget_api_passphrase

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        msg = timestamp + method.upper() + path + body
        return base64.b64encode(
            hmac.new(self._secret.encode(), msg.encode(), hashlib.sha256).digest()
        ).decode()

    def _headers(self, method: str, path: str, body: str = "") -> dict:
        ts = str(int(time.time() * 1000))
        return {
            "ACCESS-KEY":        self._key,
            "ACCESS-SIGN":       self._sign(ts, method, path, body),
            "ACCESS-TIMESTAMP":  ts,
            "ACCESS-PASSPHRASE": self._passphrase,
            "Content-Type":      "application/json",
        }

    def _get(self, path: str, params: dict = None) -> dict:
        r = requests.get(self.BASE + path, params=params,
                         headers=self._headers("GET", path), timeout=10)
        r.raise_for_status()
        return r.json().get("data", {})

    def _post(self, path: str, body: dict) -> dict:
        import json
        b = json.dumps(body)
        r = requests.post(self.BASE + path, data=b,
                          headers=self._headers("POST", path, b), timeout=10)
        r.raise_for_status()
        return r.json().get("data", {})

    def get_ticker(self, symbol: str) -> float:
        data = self._get("/api/v2/spot/market/tickers", {"symbol": symbol})
        items = data if isinstance(data, list) else [data]
        return float(items[0]["lastPr"])

    def get_balance(self, coin: str) -> float:
        items = self._get("/api/v2/spot/account/assets") or []
        for item in items:
            if item.get("coin") == coin:
                return float(item.get("available", 0))
        return 0.0

    def place_order(self, symbol: str, side: str, price: float, size: float) -> str:
        data = self._post("/api/v2/spot/trade/place-order", {
            "symbol": symbol, "side": side,
            "orderType": "limit",
            "price": str(round(price, 2)),
            "size":  str(round(size, 6)),
            "force": "gtc",
        })
        return data.get("orderId", "")

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        self._post("/api/v2/spot/trade/cancel-order",
                   {"symbol": symbol, "orderId": order_id})
        return True
```

- [ ] **Step 4: Ejecutar tests**

```bash
python -m pytest tests/services/executor/test_bitget_client.py -v
```
Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add services/executor/crypto/bitget_client.py tests/services/executor/test_bitget_client.py
git commit -m "feat: add BitgetClient with order and balance management"
```

---

## Task 6: Executor Crypto — Binance Client + Router

**Files:**
- Create: `services/executor/crypto/binance_client.py`
- Create: `services/executor/crypto/router.py`
- Create: `tests/services/executor/test_binance_client.py`
- Create: `tests/services/executor/test_router.py`

**Interfaces:**
- Consumes: `shared.config.settings` (binance_api_key, binance_api_secret)
- Produce:
  - `BinanceClient.get_ticker(symbol: str) -> float`
  - `BinanceClient.get_balance(asset: str) -> float`
  - `BinanceClient.place_order(symbol: str, side: str, price: float, quantity: float) -> str`
  - `ExchangeRouter.best_exchange(symbol: str) -> str` — retorna "bitget" o "binance"
  - `ExchangeRouter.place_order(symbol: str, side: str, price: float, size: float) -> str`

- [ ] **Step 1: Escribir tests**

```python
# tests/services/executor/test_binance_client.py
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_requests():
    with patch("services.executor.crypto.binance_client.requests") as m:
        yield m


def _mock_response(mock_requests, json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    mock_requests.get.return_value = resp
    mock_requests.post.return_value = resp
    return resp


def test_get_ticker(mock_requests):
    from services.executor.crypto.binance_client import BinanceClient
    _mock_response(mock_requests, {"price": "65000.50"})
    assert BinanceClient().get_ticker("BTCUSDT") == 65000.50


def test_get_balance(mock_requests):
    from services.executor.crypto.binance_client import BinanceClient
    _mock_response(mock_requests, [
        {"asset": "BTC",  "free": "0.001"},
        {"asset": "USDT", "free": "300.0"},
    ])
    assert BinanceClient().get_balance("USDT") == 300.0


def test_place_order(mock_requests):
    from services.executor.crypto.binance_client import BinanceClient
    _mock_response(mock_requests, {"orderId": 12345678})
    oid = BinanceClient().place_order("BTCUSDT", "buy", 64900.0, 0.001)
    assert oid == "12345678"
```

```python
# tests/services/executor/test_router.py
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
```

- [ ] **Step 2: Verificar que fallan**

```bash
python -m pytest tests/services/executor/test_binance_client.py tests/services/executor/test_router.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Crear binance_client.py**

```python
# services/executor/crypto/binance_client.py
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode
from shared.config import settings


class BinanceClient:
    BASE = "https://api.binance.com"

    def __init__(self):
        self._key    = settings.binance_api_key
        self._secret = settings.binance_api_secret

    def _sign(self, params: dict) -> str:
        return hmac.new(
            self._secret.encode(),
            urlencode(params).encode(),
            hashlib.sha256,
        ).hexdigest()

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self._key}

    def get_ticker(self, symbol: str) -> float:
        r = requests.get(f"{self.BASE}/api/v3/ticker/price",
                         params={"symbol": symbol}, timeout=10)
        r.raise_for_status()
        return float(r.json()["price"])

    def get_balance(self, asset: str) -> float:
        ts = int(time.time() * 1000)
        params = {"timestamp": ts}
        params["signature"] = self._sign(params)
        r = requests.get(f"{self.BASE}/api/v3/account",
                         params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        for b in r.json():
            if b.get("asset") == asset:
                return float(b["free"])
        return 0.0

    def place_order(self, symbol: str, side: str, price: float, quantity: float) -> str:
        ts = int(time.time() * 1000)
        params = {
            "symbol":      symbol,
            "side":        side.upper(),
            "type":        "LIMIT",
            "timeInForce": "GTC",
            "price":       str(round(price, 2)),
            "quantity":    str(round(quantity, 6)),
            "timestamp":   ts,
        }
        params["signature"] = self._sign(params)
        r = requests.post(f"{self.BASE}/api/v3/order",
                          params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return str(r.json()["orderId"])
```

- [ ] **Step 4: Crear router.py**

```python
# services/executor/crypto/router.py
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
```

- [ ] **Step 5: Ejecutar tests**

```bash
python -m pytest tests/services/executor/ -v
```
Expected: 7 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add services/executor/crypto/ tests/services/executor/
git commit -m "feat: add BinanceClient and ExchangeRouter"
```

---

## Task 7: Risk Service

**Files:**
- Create: `risk/rules.py`
- Create: `risk/service.py`
- Create: `tests/risk/test_rules.py`

**Interfaces:**
- Consumes: `shared.config.settings` (stop_on_drawdown_pct, max_daily_drawdown_pct), `shared.models.RiskState`, `shared.state.publish`, `shared.events.RISK_ALERT`
- Produce:
  - `check_drawdown(state: RiskState, config: Settings) -> str | None` — retorna nivel de alerta o None
  - `RiskService.run() -> None` — loop: lee RiskState de Redis cada 10s, aplica reglas, publica alertas

- [ ] **Step 1: Escribir tests**

```python
# tests/risk/test_rules.py
from shared.models import RiskState
from shared.config import Settings


def _settings(**kwargs) -> Settings:
    base = {"stop_on_drawdown_pct": 6.0, "max_daily_drawdown_pct": 6.0, "max_exposure_pct": 90.0}
    base.update(kwargs)
    return Settings(**base)


def test_no_alert_under_threshold():
    from risk.rules import check_drawdown
    state = RiskState(total_equity=1000.0, drawdown_pct=1.0)
    assert check_drawdown(state, _settings()) is None


def test_warning_at_2pct():
    from risk.rules import check_drawdown
    state = RiskState(total_equity=1000.0, drawdown_pct=2.5)
    assert check_drawdown(state, _settings()) == "WARNING"


def test_critical_at_4pct():
    from risk.rules import check_drawdown
    state = RiskState(total_equity=1000.0, drawdown_pct=4.5)
    assert check_drawdown(state, _settings()) == "CRITICAL"


def test_stop_at_6pct():
    from risk.rules import check_drawdown
    state = RiskState(total_equity=1000.0, drawdown_pct=6.1)
    assert check_drawdown(state, _settings()) == "STOP"


def test_exposure_alert():
    from risk.rules import check_exposure
    state = RiskState(total_equity=1000.0, exposure_pct=95.0)
    assert check_exposure(state, _settings()) == "HIGH_EXPOSURE"


def test_exposure_ok():
    from risk.rules import check_exposure
    state = RiskState(total_equity=1000.0, exposure_pct=80.0)
    assert check_exposure(state, _settings()) is None
```

- [ ] **Step 2: Verificar que fallan**

```bash
python -m pytest tests/risk/test_rules.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Crear risk/rules.py**

```python
# risk/rules.py
from shared.models import RiskState
from shared.config import Settings


def check_drawdown(state: RiskState, config: Settings) -> str | None:
    dd = state.drawdown_pct
    if dd >= config.stop_on_drawdown_pct:
        return "STOP"
    if dd >= 4.0:
        return "CRITICAL"
    if dd >= 2.0:
        return "WARNING"
    return None


def check_exposure(state: RiskState, config: Settings) -> str | None:
    if state.exposure_pct >= config.max_exposure_pct:
        return "HIGH_EXPOSURE"
    return None
```

- [ ] **Step 4: Crear risk/service.py**

```python
# risk/service.py
import time
from shared import events
from shared.config import settings
from shared.models import RiskState
from shared.state import get_state, set_state, publish
from risk.rules import check_drawdown, check_exposure


class RiskService:
    def run(self) -> None:
        print("[RiskService] Iniciado — monitoreando cada 10s")
        while True:
            self._tick()
            time.sleep(10)

    def _tick(self) -> None:
        raw = get_state("risk")
        if not raw:
            return
        state = RiskState.model_validate(raw)

        alerts = []
        if (level := check_drawdown(state, settings)):
            alerts.append({"type": "DRAWDOWN", "level": level,
                            "value": state.drawdown_pct})
            if level == "STOP":
                state.is_stopped = True
                set_state("risk", state.model_dump())

        if (level := check_exposure(state, settings)):
            alerts.append({"type": "EXPOSURE", "level": level,
                            "value": state.exposure_pct})

        for alert in alerts:
            publish(events.RISK_ALERT, alert)
            print(f"[RiskService] ALERT: {alert}")


if __name__ == "__main__":
    RiskService().run()
```

- [ ] **Step 5: Ejecutar tests**

```bash
python -m pytest tests/risk/test_rules.py -v
```
Expected: 6 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add risk/ tests/risk/
git commit -m "feat: add Risk Service with drawdown and exposure rules"
```

---

## Task 8: Dashboard API Mínimo

**Files:**
- Create: `services/dashboard/api/main.py`
- Create: `services/dashboard/api/routes/status.py`
- Create: `services/dashboard/api/routes/pnl.py`

**Interfaces:**
- Consumes: `shared.state.get_state`, `shared.events.STATE_RISK`, `shared.events.STATE_PRICES`
- Produce:
  - `GET /health` → `{"status": "ok"}`
  - `GET /status` → estado de servicios activos + RiskState actual
  - `GET /pnl` → P&L total, diario, drawdown

- [ ] **Step 1: Crear routes/status.py**

```python
# services/dashboard/api/routes/status.py
from fastapi import APIRouter
from shared.state import get_state

router = APIRouter()


@router.get("/status")
def get_status():
    risk = get_state("risk") or {}
    prices = get_state("prices") or {}
    return {
        "services": {"risk": "up", "data": "up"},
        "risk": {
            "drawdown_pct":  risk.get("drawdown_pct", 0.0),
            "is_stopped":    risk.get("is_stopped", False),
            "exposure_pct":  risk.get("exposure_pct", 0.0),
        },
        "prices": prices,
    }
```

- [ ] **Step 2: Crear routes/pnl.py**

```python
# services/dashboard/api/routes/pnl.py
from fastapi import APIRouter
from shared.state import get_state

router = APIRouter()


@router.get("/pnl")
def get_pnl():
    risk = get_state("risk") or {}
    return {
        "total_equity":  risk.get("total_equity", 0.0),
        "daily_pnl":     risk.get("daily_pnl", 0.0),
        "daily_pnl_pct": risk.get("daily_pnl_pct", 0.0),
        "drawdown_pct":  risk.get("drawdown_pct", 0.0),
    }
```

- [ ] **Step 3: Crear main.py**

```python
# services/dashboard/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.dashboard.api.routes.status import router as status_router
from services.dashboard.api.routes.pnl    import router as pnl_router

app = FastAPI(title="AlgoCore Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status_router)
app.include_router(pnl_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Verificar que el servidor arranca**

```bash
cd H:\Dev-Drive\AlgoCore
uvicorn services.dashboard.api.main:app --port 8080 --reload
```
Expected: servidor en `http://127.0.0.1:8080/docs` sin errores

Probar en browser: `http://127.0.0.1:8080/health` → `{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add services/dashboard/
git commit -m "feat: add FastAPI dashboard with /status, /pnl, /health endpoints"
```

---

## Task 9: Smoke Test de Integración

**Files:**
- Create: `tests/test_integration_smoke.py`

**Interfaces:**
- Consumes: todos los módulos creados en Tasks 1-8
- Produce: test que verifica que los módulos se importan y el flujo básico funciona

- [ ] **Step 1: Escribir smoke test**

```python
# tests/test_integration_smoke.py
"""
Smoke test: verifica que todos los módulos se importan correctamente
y que el flujo básico publish → get_state funciona con Redis mockeado.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


def test_all_modules_import():
    from shared.config import settings
    from shared.models import PriceTick, Signal, Order, RiskState, Exchange
    from shared import events
    from services.data.feeds.bitget_feed  import BitgetFeed
    from services.data.feeds.binance_feed import BinanceFeed
    from services.executor.crypto.bitget_client  import BitgetClient
    from services.executor.crypto.binance_client import BinanceClient
    from services.executor.crypto.router import ExchangeRouter
    from risk.rules import check_drawdown, check_exposure
    assert True  # si llegamos aquí, todas las importaciones funcionan


def test_price_tick_flow():
    """PriceTick publicado por feed → puede deserializarse como PriceTick."""
    from shared.models import PriceTick, Exchange
    from services.data.feeds.bitget_feed import BitgetFeed

    published = {}
    with patch("shared.state.publish") as mock_pub:
        mock_pub.side_effect = lambda ch, d: published.update({"channel": ch, "data": d})
        feed = BitgetFeed(["ETHUSDT"])
        feed._on_message({
            "action": "snapshot",
            "data": [{"instId": "ETHUSDT", "last": "2500.00", "vol24h": "1000"}],
        })

    assert published["channel"] == "price:tick"
    tick = PriceTick(
        **{k: published["data"][k] for k in ["symbol", "price", "volume", "timestamp"]},
        exchange=Exchange(published["data"]["exchange"]),
    )
    assert tick.price == 2500.0


def test_risk_rules_stop_flow():
    from shared.models import RiskState
    from shared.config import Settings
    from risk.rules import check_drawdown

    state    = RiskState(total_equity=1000.0, drawdown_pct=7.0)
    cfg      = Settings(stop_on_drawdown_pct=6.0)
    result   = check_drawdown(state, cfg)
    assert result == "STOP"
```

- [ ] **Step 2: Ejecutar**

```bash
python -m pytest tests/test_integration_smoke.py -v
```
Expected: 3 tests PASSED

- [ ] **Step 3: Ejecutar suite completa**

```bash
python -m pytest tests/ -v --tb=short
```
Expected: todos los tests PASSED, 0 failures

- [ ] **Step 4: Commit final de Phase 1**

```bash
git add tests/test_integration_smoke.py
git commit -m "test: add Phase 1 integration smoke test

Verifica imports de todos los módulos y flujo básico:
PriceTick publish, Risk rules STOP, deserialización de modelos."
```

---

## Verificación Final Phase 1

Antes de declarar Phase 1 completa, verificar:

- [ ] `docker-compose up` levanta Redis y PostgreSQL sin errores
- [ ] `python -m pytest tests/ -v` — 0 failures
- [ ] `python services/data/service.py` conecta WebSocket de Bitget y Binance (requiere internet)
- [ ] `uvicorn services.dashboard.api.main:app --port 8080` responde en `/health`
- [ ] `GET /status` devuelve estructura correcta (aunque con datos vacíos)

---

## Próximos Planes

- **Plan 2/4** — ML Service (XGBoost + LSTM + Ensemble + MLflow) → `2026-06-20-algocore-phase2-ml.md`
- **Plan 3/4** — Forex + RL Service (MT5 Bridge + Stable-Baselines3) → `2026-06-20-algocore-phase3-forex-rl.md`
- **Plan 4/4** — Dashboard completo + Telegram + VPS deployment → `2026-06-20-algocore-phase4-production.md`

---

*Plan generado con writing-plans skill — 2026-06-20*  
*Spec fuente: docs/superpowers/specs/2026-06-20-algocore-trading-system-design.md*
