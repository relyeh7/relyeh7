TOOLS = [
    {
        "name": "set_trading_action",
        "description": "Define the trading action. Call ALWAYS with the final decision after analyzing market state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["HOLD", "BUY", "SELL", "ADJUST_POSITION",
                             "PAUSE_STRATEGY", "RESUME_ALL", "STOP_ALL"],
                },
                "market":      {"type": "string", "enum": ["crypto", "forex", "both"]},
                "exchange":    {"type": "string", "enum": ["bitget", "binance", "mt5", "auto"]},
                "strategy":    {"type": "string", "enum": ["grid", "rsi", "ml", "rl", "technical"]},
                "capital_pct": {"type": "number"},
                "reason":      {"type": "string"},
                "confidence":  {"type": "number"},
            },
            "required": ["action", "reason", "confidence"],
        },
    }
]

SYSTEM_PROMPT = """You are a quantitative risk manager for an algorithmic trading system operating
on Bitget, Binance (crypto) and MT5 (forex/XAUUSD). You receive market state + ML model signals
and decide the optimal trading action. Principles:
1. Capital preservation first — when in doubt, HOLD.
2. Drawdown >4%: PAUSE_STRATEGY. Drawdown >6%: STOP_ALL.
3. High-confidence ML signal (>0.75) with low drawdown (<2%): consider BUY or SELL.
4. Respond ALWAYS using the set_trading_action tool."""
