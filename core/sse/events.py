"""SSE event broadcasting via Redis pub/sub."""

import json
import logging

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def broadcast_event(channel: str, event_type: str, data: dict) -> None:
    """Publish an SSE event to a Redis channel.

    Args:
        channel: Channel name — typically "user:{user_id}" or "org:{org_id}".
        event_type: Event type string (e.g. "notification.created").
        data: JSON-serialisable payload.
    """
    try:
        message = json.dumps({"type": event_type, "data": data})
        _get_redis().publish(f"sse:{channel}", message)
    except Exception:
        logger.exception(
            "Failed to broadcast SSE event type=%s channel=%s", event_type, channel
        )


def sse_stream(channel: str):
    r"""Generator that yields SSE-formatted messages from a Redis pub/sub channel.

    Yields formatted SSE strings: ``data: {...}\n\n``

    Args:
        channel: Redis channel to subscribe to.
    """
    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(f"sse:{channel}")

    try:
        yield 'data: {"type": "connected"}\n\n'
        for message in pubsub.listen():
            if message["type"] == "message":
                yield f"data: {message['data']}\n\n"
    finally:
        pubsub.unsubscribe()
        pubsub.close()
