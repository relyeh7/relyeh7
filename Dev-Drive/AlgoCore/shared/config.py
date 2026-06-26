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

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id:   str = ""

    # Sentiment
    cryptopanic_api_key: str = ""

    # Trading
    trading_symbol: str = "BTCUSDT"
    paper_trading:    bool      = True
    trading_symbols:  list[str] = ["BTCUSDT"]
    api_key:          str       = ""

    # Phase 6 — risk management
    stop_loss_pct:    float = 2.0
    take_profit_pct:  float = 4.0
    kelly_fraction:   float = 0.25
    feed_poll_sec:    int   = 30
    initial_equity:   float = 10_000.0

    # MLflow
    mlflow_tracking_uri: str = "mlruns"


settings = Settings()
