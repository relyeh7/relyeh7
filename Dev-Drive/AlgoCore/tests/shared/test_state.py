import json
import pytest
from unittest.mock import MagicMock, patch, call


@pytest.fixture(autouse=True)
def patch_redis():
    with patch("shared.state._redis") as mock:
        yield mock


def test_publish_adds_to_stream(patch_redis):
    from shared.state import publish
    publish("price:tick", {"price": 2500.0})
    patch_redis.xadd.assert_called_once()
    args = patch_redis.xadd.call_args
    assert args[0][0] == "price:tick"
    payload = json.loads(args[0][1]["payload"])
    assert payload["price"] == 2500.0


def test_set_state_stores_json(patch_redis):
    from shared.state import set_state
    set_state("risk", {"drawdown": 1.5})
    patch_redis.set.assert_called_once_with(
        "state:risk", json.dumps({"drawdown": 1.5})
    )


def test_get_state_returns_none_when_missing(patch_redis):
    from shared.state import get_state
    patch_redis.get.return_value = None
    result = get_state("nonexistent")
    assert result is None


def test_get_state_deserializes_json(patch_redis):
    from shared.state import get_state
    patch_redis.get.return_value = json.dumps({"equity": 1000.0})
    result = get_state("risk")
    assert result["equity"] == 1000.0


def test_subscribe_once_returns_payloads(patch_redis):
    from shared.state import subscribe_once
    payload = json.dumps({"price": 2500.0})
    patch_redis.xread.return_value = [
        ("price:tick", [("1-0", {"payload": payload})])
    ]
    results = subscribe_once("price:tick", "$")
    assert len(results) == 1
    assert results[0]["price"] == 2500.0


def test_subscribe_since_returns_tuple():
    with patch("shared.state._redis") as mock_redis:
        mock_redis.xread.return_value = []
        from shared.state import subscribe_since
        result = subscribe_since("price:tick")
    assert isinstance(result, tuple)
    assert len(result) == 2
    payloads, last_id = result
    assert isinstance(payloads, list)
    assert isinstance(last_id, str)


def test_subscribe_since_returns_last_stream_id():
    import json
    fake_payload = {"symbol": "BTCUSDT", "price": 50000.0}
    fake_stream_id = "1718000000000-0"
    fake_xread = [("price:tick", [(fake_stream_id, {"payload": json.dumps(fake_payload)})])]
    with patch("shared.state._redis") as mock_redis:
        mock_redis.xread.return_value = fake_xread
        from shared.state import subscribe_since
        payloads, last_id = subscribe_since("price:tick", last_id="0")
    assert len(payloads) == 1
    assert payloads[0] == fake_payload
    assert last_id == fake_stream_id  # Real Redis stream ID, not ISO timestamp


def test_subscribe_since_returns_input_id_on_empty():
    with patch("shared.state._redis") as mock_redis:
        mock_redis.xread.return_value = []
        from shared.state import subscribe_since
        payloads, last_id = subscribe_since("price:tick", last_id="123456-0")
    assert payloads == []
    assert last_id == "123456-0"  # unchanged
