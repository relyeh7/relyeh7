from unittest.mock import patch, MagicMock


def _mock_bitget_response():
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = {
        "code": "00000",
        "data": [
            ["1711382400000", "3200.00", "3210.00", "3195.00", "3205.00", "1200.5", "0", "0", "0"],
            ["1711383300000", "3205.00", "3215.00", "3200.00", "3210.00", "1100.3", "0", "0", "0"],
        ]
    }
    return m


def _mock_binance_response():
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = [
        [1711382400000, "3200.00", "3210.00", "3195.00", "3205.00", "1200.5",
         1711383299999, "0", 100, "0", "0", "0"],
        [1711383300000, "3205.00", "3215.00", "3200.00", "3210.00", "1100.3",
         1711384199999, "0", 120, "0", "0", "0"],
    ]
    return m


def test_get_candles_bitget_returns_dataframe():
    with patch("services.ml.data.fetcher.requests.get", return_value=_mock_bitget_response()):
        from services.ml.data.fetcher import OHLCVFetcher
        df = OHLCVFetcher().get_candles("ETHUSDT", exchange="bitget", limit=2)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df["close"].iloc[0] == 3205.0
    assert isinstance(df["volume"].iloc[0], float)


def test_get_candles_binance_returns_dataframe():
    with patch("services.ml.data.fetcher.requests.get", return_value=_mock_binance_response()):
        from services.ml.data.fetcher import OHLCVFetcher
        df = OHLCVFetcher().get_candles("ETHUSDT", exchange="binance", limit=2)
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df["open"].iloc[1] == 3205.0


def test_get_candles_unknown_exchange_raises():
    from services.ml.data.fetcher import OHLCVFetcher
    try:
        OHLCVFetcher().get_candles("ETHUSDT", exchange="unknown")
        assert False, "should raise"
    except ValueError:
        pass
