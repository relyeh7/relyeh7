import time
from datetime import datetime, timezone

from shared import events
from shared.config import settings
from shared.state import publish
from services.orchestrator.context import build_context
from services.orchestrator.agent import OrchestratorAgent


class OrchestratorService:
    INTERVAL_SEC = 900  # 15 minutes

    def __init__(self):
        self._agent = OrchestratorAgent(
            anthropic_key=settings.anthropic_api_key,
            gemini_key=settings.gemini_api_key,
        )
        self._last_signal_id = "0"

    def _run_once(self) -> None:
        try:
            context, risk, signals, self._last_signal_id = build_context(self._last_signal_id)
            decision = self._agent.decide(context, risk, signals)
            decision["timestamp"] = datetime.now(timezone.utc).isoformat()
            publish(events.ORCH_DECISION, decision)
            print(f"[Orchestrator] {decision['action']} — {decision['reason'][:60]}")
        except Exception as e:
            print(f"[Orchestrator] error: {e}")

    def run(self) -> None:
        print("[Orchestrator] Starting 15-min decision loop")
        while True:
            self._run_once()
            time.sleep(self.INTERVAL_SEC)


if __name__ == "__main__":
    OrchestratorService().run()
