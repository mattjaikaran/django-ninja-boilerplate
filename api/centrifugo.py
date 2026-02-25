"""Centrifugo real-time messaging integration.

Provides JWT token generation for client authentication and an HTTP client
for publishing messages from Django to Centrifugo.

Architecture:
    Client <-> Centrifugo (WebSocket, port 8800)
    Django -> Centrifugo (HTTP API, publish/presence/history)
    Centrifugo <-> Redis (PUB/SUB engine)
"""

import logging
import time
from typing import Any

import httpx
import jwt
from django.conf import settings

logger = logging.getLogger(__name__)


def generate_connection_token(
    user_id: str,
    info: dict[str, Any] | None = None,
    expire_at: int | None = None,
) -> str:
    """Generate a Centrifugo connection JWT token.

    Args:
        user_id: The user identifier (becomes the `sub` claim).
        info: Optional dict attached to the connection (visible in presence).
        expire_at: Unix timestamp when the token expires.
            Defaults to now + CENTRIFUGO_TOKEN_TTL.
    """
    now = int(time.time())
    if expire_at is None:
        expire_at = now + getattr(settings, "CENTRIFUGO_TOKEN_TTL", 3600)

    claims: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire_at,
    }
    if info:
        claims["info"] = info

    return jwt.encode(
        claims,
        settings.CENTRIFUGO_TOKEN_SECRET,
        algorithm="HS256",
    )


def generate_subscription_token(
    user_id: str,
    channel: str,
    info: dict[str, Any] | None = None,
    expire_at: int | None = None,
) -> str:
    """Generate a Centrifugo subscription JWT token.

    Required for subscribing to channels with `allow_subscribe_for_client` disabled
    (private/protected channels).

    Args:
        user_id: The user identifier.
        channel: The Centrifugo channel name (e.g. "chat:abc123").
        info: Optional dict attached to the subscription.
        expire_at: Unix timestamp when the token expires.
    """
    now = int(time.time())
    if expire_at is None:
        expire_at = now + getattr(settings, "CENTRIFUGO_TOKEN_TTL", 3600)

    claims: dict[str, Any] = {
        "sub": str(user_id),
        "channel": channel,
        "iat": now,
        "exp": expire_at,
    }
    if info:
        claims["info"] = info

    return jwt.encode(
        claims,
        settings.CENTRIFUGO_TOKEN_SECRET,
        algorithm="HS256",
    )


class CentrifugoClient:
    """HTTP client for Centrifugo server API.

    Uses httpx to call Centrifugo's HTTP API for publishing messages,
    managing subscriptions, and querying presence/history.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        timeout: float = 5.0,
    ):
        self.url = (
            url or getattr(settings, "CENTRIFUGO_URL", "http://localhost:8800")
        ).rstrip("/")
        self.api_key = api_key or getattr(settings, "CENTRIFUGO_API_KEY", "")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

    def _request(self, method: str, data: dict[str, Any]) -> dict[str, Any]:
        """Send a request to Centrifugo's HTTP API."""
        payload = {"method": method, "params": data}
        try:
            response = httpx.post(
                f"{self.url}/api",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("error"):
                logger.error("Centrifugo API error: %s", result["error"])
            return result
        except httpx.HTTPError:
            logger.exception("Centrifugo request failed: %s", method)
            raise

    def publish(self, channel: str, data: dict[str, Any]) -> dict[str, Any]:
        """Publish a message to a channel."""
        return self._request("publish", {"channel": channel, "data": data})

    def broadcast(self, channels: list[str], data: dict[str, Any]) -> dict[str, Any]:
        """Publish a message to multiple channels."""
        return self._request("broadcast", {"channels": channels, "data": data})

    def subscribe(self, user: str, channel: str) -> dict[str, Any]:
        """Subscribe a user to a channel (server-side)."""
        return self._request("subscribe", {"user": user, "channel": channel})

    def unsubscribe(self, user: str, channel: str) -> dict[str, Any]:
        """Unsubscribe a user from a channel (server-side)."""
        return self._request("unsubscribe", {"user": user, "channel": channel})

    def disconnect(self, user: str) -> dict[str, Any]:
        """Disconnect a user from the server."""
        return self._request("disconnect", {"user": user})

    def presence(self, channel: str) -> dict[str, Any]:
        """Get presence information for a channel."""
        return self._request("presence", {"channel": channel})

    def history(self, channel: str, limit: int = 50) -> dict[str, Any]:
        """Get message history for a channel."""
        return self._request("history", {"channel": channel, "limit": limit})


# Module-level singleton — import and use directly.
centrifugo_client = CentrifugoClient()
