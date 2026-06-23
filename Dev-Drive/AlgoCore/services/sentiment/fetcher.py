import requests
from shared.models import SentimentState


class SentimentFetcher:
    _FNG_URL = "https://api.alternative.me/fng/?limit=1"
    _PANIC_URL = "https://cryptopanic.com/api/v1/posts/?auth_token={token}&currencies=BTC,ETH&filter=important"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def fetch(self) -> SentimentState:
        try:
            fear_greed = self._fetch_fear_greed()
            news = self._fetch_news_sentiment()
            return SentimentState(fear_greed_score=fear_greed, news_sentiment=news)
        except Exception:
            return SentimentState(fear_greed_score=0.5, news_sentiment=0.5)

    def _fetch_fear_greed(self) -> float:
        resp = requests.get(self._FNG_URL, timeout=10)
        resp.raise_for_status()
        value = int(resp.json()["data"][0]["value"])
        return round(value / 100.0, 4)

    def _fetch_news_sentiment(self) -> float:
        if not self._api_key:
            return 0.5
        url = self._PANIC_URL.format(token=self._api_key)
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return 0.5
        results = resp.json().get("results", [])
        if not results:
            return 0.5
        liked = sum(r["votes"].get("liked", 0) for r in results)
        disliked = sum(r["votes"].get("disliked", 0) for r in results)
        total = liked + disliked
        return round(liked / total, 4) if total > 0 else 0.5
