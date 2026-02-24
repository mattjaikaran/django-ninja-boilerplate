"""Centrifugo real-time service templates for generated apps.

These templates generate service classes that use Centrifugo (via the
api.centrifugo module) instead of Django Channels consumers. Django stays
WSGI — all WebSocket connections are handled by Centrifugo.
"""

CHAT_REALTIME_SERVICE_TEMPLATE = '''"""Real-time chat service using Centrifugo."""

import logging
from typing import Any

from api.centrifugo import centrifugo_client, generate_subscription_token

logger = logging.getLogger(__name__)


class ChatRealtimeService:
    """Publish chat events to Centrifugo channels.

    Channel naming: ``chat:<conversation_id>``

    Clients subscribe to their conversation channels after connecting to
    Centrifugo with a connection token. Subscription tokens are obtained
    from ``/api/realtime/subscription-token``.
    """

    NAMESPACE = "chat"

    @classmethod
    def channel_name(cls, conversation_id: str) -> str:
        """Build the Centrifugo channel name for a conversation."""
        return f"{{cls.NAMESPACE}}:{{conversation_id}}"

    @classmethod
    def publish_message(
        cls,
        conversation_id: str,
        message_data: dict[str, Any],
    ) -> None:
        """Publish a new message to the conversation channel."""
        channel = cls.channel_name(conversation_id)
        try:
            centrifugo_client.publish(channel, {{
                "type": "chat_message",
                "message": message_data,
            }})
        except Exception:
            logger.exception("Failed to publish chat message to %s", channel)

    @classmethod
    def publish_typing(
        cls,
        conversation_id: str,
        user_id: str,
        username: str,
        is_typing: bool = True,
    ) -> None:
        """Publish a typing indicator to the conversation channel."""
        channel = cls.channel_name(conversation_id)
        try:
            centrifugo_client.publish(channel, {{
                "type": "typing_indicator",
                "user_id": user_id,
                "username": username,
                "is_typing": is_typing,
            }})
        except Exception:
            logger.exception("Failed to publish typing indicator to %s", channel)

    @classmethod
    def publish_read_receipt(
        cls,
        conversation_id: str,
        user_id: str,
        timestamp: str,
    ) -> None:
        """Publish a read receipt to the conversation channel."""
        channel = cls.channel_name(conversation_id)
        try:
            centrifugo_client.publish(channel, {{
                "type": "read_receipt",
                "user_id": user_id,
                "timestamp": timestamp,
            }})
        except Exception:
            logger.exception("Failed to publish read receipt to %s", channel)

    @classmethod
    def get_presence(cls, conversation_id: str) -> dict[str, Any]:
        """Get online users in a conversation."""
        channel = cls.channel_name(conversation_id)
        return centrifugo_client.presence(channel)

    @classmethod
    def get_subscription_token(
        cls,
        user_id: str,
        conversation_id: str,
    ) -> str:
        """Generate a subscription token for a chat channel."""
        channel = cls.channel_name(conversation_id)
        return generate_subscription_token(user_id=user_id, channel=channel)
'''

NOTIFICATION_REALTIME_SERVICE_TEMPLATE = '''"""Real-time notification service using Centrifugo."""

import logging
from typing import Any

from api.centrifugo import centrifugo_client

logger = logging.getLogger(__name__)


class NotificationRealtimeService:
    """Push notifications to users via Centrifugo.

    Channel naming: ``notifications:<user_id>``

    Each user subscribes to their personal notification channel.
    """

    NAMESPACE = "notifications"

    @classmethod
    def channel_name(cls, user_id: str) -> str:
        """Build the Centrifugo channel name for a user's notifications."""
        return f"{{cls.NAMESPACE}}:{{user_id}}"

    @classmethod
    def send_notification(
        cls,
        user_id: str,
        notification_data: dict[str, Any],
    ) -> None:
        """Push a notification to a user's channel."""
        channel = cls.channel_name(user_id)
        try:
            centrifugo_client.publish(channel, {{
                "type": "notification",
                "data": notification_data,
            }})
        except Exception:
            logger.exception("Failed to send notification to %s", channel)

    @classmethod
    def broadcast_notification(
        cls,
        user_ids: list[str],
        notification_data: dict[str, Any],
    ) -> None:
        """Push a notification to multiple users."""
        channels = [cls.channel_name(uid) for uid in user_ids]
        try:
            centrifugo_client.broadcast(channels, {{
                "type": "notification",
                "data": notification_data,
            }})
        except Exception:
            logger.exception("Failed to broadcast notification to %d users", len(user_ids))
'''

ORGANIZATION_REALTIME_SERVICE_TEMPLATE = '''"""Real-time organization service using Centrifugo."""

import logging
from typing import Any

from api.centrifugo import centrifugo_client, generate_subscription_token

logger = logging.getLogger(__name__)


class OrganizationRealtimeService:
    """Publish organization-wide events via Centrifugo.

    Channel naming: ``organization:<organization_id>``

    All members of an organization subscribe to the org channel for
    real-time updates (member joins/leaves, announcements, etc.).
    """

    NAMESPACE = "organization"

    @classmethod
    def channel_name(cls, organization_id: str) -> str:
        """Build the Centrifugo channel name for an organization."""
        return f"{{cls.NAMESPACE}}:{{organization_id}}"

    @classmethod
    def publish_event(
        cls,
        organization_id: str,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """Publish an event to the organization channel."""
        channel = cls.channel_name(organization_id)
        try:
            centrifugo_client.publish(channel, {{
                "type": event_type,
                "data": event_data,
            }})
        except Exception:
            logger.exception("Failed to publish org event to %s", channel)

    @classmethod
    def get_presence(cls, organization_id: str) -> dict[str, Any]:
        """Get online members of an organization."""
        channel = cls.channel_name(organization_id)
        return centrifugo_client.presence(channel)

    @classmethod
    def get_subscription_token(
        cls,
        user_id: str,
        organization_id: str,
    ) -> str:
        """Generate a subscription token for an organization channel."""
        channel = cls.channel_name(organization_id)
        return generate_subscription_token(user_id=user_id, channel=channel)
'''
