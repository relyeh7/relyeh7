import time
from shared.config import settings
from shared.state import publish, set_state
from shared import events
from services.sentiment.fetcher import SentimentFetcher


class SentimentService:
    def __init__(self, interval: int = 900):
        self._fetcher = SentimentFetcher(api_key=settings.cryptopanic_api_key)
        self._interval = interval

    def _run_once(self) -> None:
        state = self._fetcher.fetch()
        payload = state.model_dump()
        publish(events.SENTIMENT_UPDATE, payload)
        set_state("sentiment", payload)

    def run(self) -> None:
        while True:
            self._run_once()
            time.sleep(self._interval)


if __name__ == "__main__":
    SentimentService().run()
