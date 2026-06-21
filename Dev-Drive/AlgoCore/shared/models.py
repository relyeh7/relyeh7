from datetime import datetime, timezone
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


class OHLCVBar(BaseModel):
    timestamp: str
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float


class OrchestratorDecision(BaseModel):
    action:      str                          # HOLD|BUY|SELL|ADJUST_POSITION|PAUSE_STRATEGY|RESUME_ALL|STOP_ALL
    market:      str  = "crypto"              # crypto|forex|both
    exchange:    str  = "auto"                # bitget|binance|mt5|auto
    strategy:    str  = "ml"                  # grid|rsi|ml|rl|technical
    capital_pct: float = Field(ge=0.0, le=1.0, default=0.0)
    reason:      str  = ""
    confidence:  float = Field(ge=0.0, le=1.0, default=0.5)
    timestamp:   str  = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
