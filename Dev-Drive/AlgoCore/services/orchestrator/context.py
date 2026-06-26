from shared.state import get_state, subscribe_since
from shared.config import settings
from shared import events


def build_context(last_signal_id: str = "0") -> tuple[str, dict, list[dict], str]:
    risk_raw = get_state("risk:state") or {}
    risk = {
        "drawdown_pct":   float(risk_raw.get("drawdown_pct", 0.0)),
        "is_stopped":     bool(risk_raw.get("is_stopped", False)),
        "exposure_pct":   float(risk_raw.get("exposure_pct", 0.0)),
        "daily_pnl_pct":  float(risk_raw.get("daily_pnl_pct", 0.0)),
        "daily_pnl":      float(risk_raw.get("daily_pnl", 0.0)),
        "total_equity":   float(risk_raw.get("total_equity", 0.0)),
        "open_positions": int(risk_raw.get("open_positions", 0)),
    }

    sentiment_raw = get_state("sentiment") or {}
    fear_greed    = sentiment_raw.get("fear_greed_score", None)
    news_sent     = sentiment_raw.get("news_sentiment", None)

    ml_signals, last_signal_id = subscribe_since(events.ML_SIGNAL, last_signal_id)

    # Read current prices from state (written by data feeds in Phase 6)
    prices: dict[str, float] = {}
    for symbol in settings.trading_symbols:
        price_state = get_state(f"price:{symbol}")
        if price_state and "price" in price_state:
            prices[symbol] = float(price_state["price"])

    signal_summary = ""
    for s in ml_signals:
        signal_summary += (
            f"  {s.get('symbol')}: {s.get('action')} "
            f"conf={s.get('confidence', 0):.2f} strategy={s.get('strategy')}\n"
        )
    if not signal_summary:
        signal_summary = "  No ML signals yet.\n"

    price_summary = ", ".join(f"{k}=${v:.2f}" for k, v in prices.items()) or "no price data"

    if fear_greed is not None:
        sentiment_section = (
            f"\n=== SENTIMENT ===\n"
            f"Fear & Greed: {fear_greed:.2f} (0=extreme fear, 1=extreme greed)\n"
            f"News sentiment: {news_sent:.2f}\n"
        )
    else:
        sentiment_section = "\n=== SENTIMENT ===\nNo sentiment data yet.\n"

    prompt = (
        f"=== MARKET STATE ===\nPrices: {price_summary}\n\n"
        f"=== RISK ===\n"
        f"Drawdown: {risk['drawdown_pct']:.2f}%  Exposure: {risk['exposure_pct']:.1f}%\n"
        f"Daily P&L: {risk['daily_pnl_pct']:+.2f}% (${risk['daily_pnl']:+.2f})  Equity: ${risk['total_equity']:.2f}\n"
        f"Stopped: {risk['is_stopped']}  Open positions: {risk['open_positions']}\n"
        f"{sentiment_section}\n"
        f"=== ML SIGNALS (last 15 min) ===\n{signal_summary}"
        f"Analyze the above and call set_trading_action with your decision."
    )
    return prompt, risk, ml_signals, last_signal_id
