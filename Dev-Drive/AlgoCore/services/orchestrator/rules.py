def apply_rules(risk: dict, signals: list[dict]) -> dict:
    dd            = float(risk.get("drawdown_pct", 0))
    stopped       = bool(risk.get("is_stopped", False))
    daily_pnl_pct = float(risk.get("daily_pnl_pct", 0.0))

    if stopped or dd >= 6.0:
        return _decision("STOP_ALL", "Drawdown ≥6% or system stopped.", 0.99)
    if daily_pnl_pct <= -5.0:
        return _decision("STOP_ALL", f"Daily loss {abs(daily_pnl_pct):.2f}% ≥5% limit.", 0.99)
    if dd >= 4.0:
        return _decision("PAUSE_STRATEGY", "Drawdown ≥4%: pausing ML/RL strategies.", 0.9)
    if dd >= 2.0:
        return _decision("HOLD", "Drawdown ≥2%: conservative hold.", 0.8)

    for sig in signals:
        conf   = float(sig.get("confidence", 0))
        action = sig.get("action", "HOLD")
        if action == "BUY"  and conf >= 0.75:
            return _decision("BUY",  f"ML BUY signal conf={conf:.2f}.", conf)
        if action == "SELL" and conf >= 0.75:
            return _decision("SELL", f"ML SELL signal conf={conf:.2f}.", conf)

    return _decision("HOLD", "No strong signal — holding current positions.", 0.6)


def _decision(action: str, reason: str, confidence: float) -> dict:
    return {
        "action": action, "market": "crypto", "exchange": "auto",
        "strategy": "ml", "capital_pct": 0.0,
        "reason": reason, "confidence": confidence,
    }
