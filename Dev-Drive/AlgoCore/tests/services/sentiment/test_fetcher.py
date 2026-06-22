from unittest.mock import patch, MagicMock


def _mock_fng_response(value: str = "52"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": [{"value": value, "value_classification": "Neutral"}]}
    return resp


def _mock_panic_response(liked: int = 12, disliked: int = 3):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "results": [{"votes": {"liked": liked, "disliked": disliked}}]
    }
    return resp


def test_fetcher_returns_sentiment_state():
    with patch("services.sentiment.fetcher.requests.get") as mock_get:
        mock_get.side_effect = [_mock_fng_response("72"), _mock_panic_response(9, 1)]
        from services.sentiment.fetcher import SentimentFetcher
        fetcher = SentimentFetcher(api_key="testtoken")
        state = fetcher.fetch()
    assert abs(state.fear_greed_score - 0.72) < 0.01
    assert abs(state.news_sentiment - 0.9) < 0.01


def test_fetcher_defaults_when_no_panic_token():
    with patch("services.sentiment.fetcher.requests.get") as mock_get:
        mock_get.return_value = _mock_fng_response("30")
        from services.sentiment.fetcher import SentimentFetcher
        fetcher = SentimentFetcher(api_key="")
        state = fetcher.fetch()
    assert abs(state.fear_greed_score - 0.30) < 0.01
    assert state.news_sentiment == 0.5


def test_fetcher_handles_fng_error():
    with patch("services.sentiment.fetcher.requests.get", side_effect=Exception("network")):
        from services.sentiment.fetcher import SentimentFetcher
        fetcher = SentimentFetcher(api_key="")
        state = fetcher.fetch()
    assert state.fear_greed_score == 0.5
    assert state.news_sentiment == 0.5
