import json
import requests as req
from anthropic import Anthropic
from services.orchestrator.tools import TOOLS, SYSTEM_PROMPT
from services.orchestrator.rules import apply_rules

MODEL_CLAUDE = "claude-haiku-4-5-20251001"
MODEL_GEMINI = "gemini-2.0-flash"
GEMINI_URL   = ("https://generativelanguage.googleapis.com/v1beta/models/"
                f"{MODEL_GEMINI}:generateContent")


class OrchestratorAgent:
    def __init__(self, anthropic_key: str, gemini_key: str):
        self._claude     = Anthropic(api_key=anthropic_key) if anthropic_key else None
        self._gemini_key = gemini_key

    def decide(self, context: str, risk: dict, signals: list[dict]) -> dict:
        if self._claude:
            try:
                resp = self._claude.messages.create(
                    model=MODEL_CLAUDE,
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": context}],
                    tools=TOOLS,
                    tool_choice={"type": "any"},
                )
                for block in resp.content:
                    if block.type == "tool_use" and block.name == "set_trading_action":
                        print("[Orchestrator] Decision via Claude Haiku")
                        return block.input
            except Exception as e:
                print(f"[Orchestrator] Claude unavailable ({e}) — trying Gemini")

        if self._gemini_key:
            result = self._call_gemini(context)
            if result:
                print("[Orchestrator] Decision via Gemini Flash")
                return result

        print("[Orchestrator] Using deterministic rules fallback")
        return apply_rules(risk, signals)

    def _call_gemini(self, context: str) -> dict | None:
        prompt = (
            SYSTEM_PROMPT + "\n\n" + context +
            '\n\nRespond ONLY with valid JSON:\n'
            '{"action":"HOLD|BUY|SELL|ADJUST_POSITION|PAUSE_STRATEGY|RESUME_ALL|STOP_ALL",'
            '"market":"crypto|forex|both","exchange":"bitget|binance|mt5|auto",'
            '"strategy":"grid|rsi|ml|rl|technical","capital_pct":0.0,'
            '"reason":"string","confidence":0.0}'
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300},
        }
        try:
            r = req.post(f"{GEMINI_URL}?key={self._gemini_key}", json=body, timeout=15)
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception as e:
            print(f"[Orchestrator] Gemini error: {e}")
            return None
