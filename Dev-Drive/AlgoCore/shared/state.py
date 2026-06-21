import json
import redis as redis_lib
from shared.config import settings

try:
    _redis = redis_lib.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
except Exception:
    _redis = None


def publish(channel: str, data: dict) -> None:
    """Publish a message to a Redis stream."""
    if _redis:
        try:
            _redis.xadd(channel, {"payload": json.dumps(data, default=str)})
        except Exception:
            pass


def set_state(key: str, data: dict) -> None:
    """Store JSON state in Redis."""
    if _redis:
        try:
            _redis.set(f"state:{key}", json.dumps(data, default=str))
        except Exception:
            pass


def get_state(key: str) -> dict | None:
    """Retrieve and deserialize JSON state from Redis."""
    if not _redis:
        return None
    try:
        val = _redis.get(f"state:{key}")
        return json.loads(val) if val else None
    except Exception:
        return None


def subscribe_once(channel: str, last_id: str = "$") -> list[dict]:
    """
    Read up to 20 messages from a stream without blocking (100ms timeout).

    Args:
        channel: Redis stream channel name
        last_id: Message ID to start reading from (default "$" for new messages)

    Returns:
        List of deserialized message payloads
    """
    if not _redis:
        return []
    try:
        msgs = _redis.xread({channel: last_id}, block=100, count=20) or []
        result = []
        for _stream, messages in msgs:
            for _msg_id, fields in messages:
                result.append(json.loads(fields["payload"]))
        return result
    except Exception:
        return []
