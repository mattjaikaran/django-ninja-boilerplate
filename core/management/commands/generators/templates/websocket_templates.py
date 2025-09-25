"""WebSocket templates for real-time chat functionality."""

CHAT_CONSUMERS_TEMPLATE = '''"""WebSocket consumers for real-time chat."""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from {app_name}.models import Conversation, ConversationParticipant, Message

User = get_user_model()
logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat messaging."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.conversation_group_name = f"chat_{{self.conversation_id}}"
        self.user = self.scope["user"]

        # Check if user is authenticated and is a participant
        if not self.user.is_authenticated:
            await self.close()
            return

        is_participant = await self.check_participant()
        if not is_participant:
            await self.close()
            return

        # Join conversation group
        await self.channel_layer.group_add(
            self.conversation_group_name,
            self.channel_name
        )

        await self.accept()

        # Send connection confirmation
        await self.send(text_data=json.dumps({{
            "type": "connection_established",
            "message": "Connected to conversation"
        }}))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave conversation group
        await self.channel_layer.group_discard(
            self.conversation_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "chat_message":
                await self.handle_chat_message(data)
            elif message_type == "typing_start":
                await self.handle_typing_start()
            elif message_type == "typing_stop":
                await self.handle_typing_stop()
            elif message_type == "mark_read":
                await self.handle_mark_read(data)
            else:
                await self.send_error("Unknown message type")

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            logger.error(f"Error in ChatConsumer.receive: {{e}}")
            await self.send_error("Server error")

    async def handle_chat_message(self, data):
        """Handle incoming chat message."""
        content = data.get("content", "").strip()
        message_type = data.get("message_type", "text")
        reply_to_id = data.get("reply_to_id")

        if not content:
            await self.send_error("Message content cannot be empty")
            return

        # Save message to database
        message = await self.save_message(content, message_type, reply_to_id)
        if not message:
            await self.send_error("Failed to save message")
            return

        # Send message to conversation group
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {{
                "type": "chat_message",
                "message": {{
                    "id": str(message.id),
                    "content": message.content,
                    "type": message.type,
                    "sender_id": str(message.sender.id),
                    "sender_username": message.sender.username,
                    "conversation_id": str(message.conversation.id),
                    "reply_to_id": str(message.reply_to.id) if message.reply_to else None,
                    "created_at": message.created_at.isoformat(),
                    "is_edited": message.is_edited,
                }}
            }}
        )

    async def handle_typing_start(self):
        """Handle typing indicator start."""
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {{
                "type": "typing_indicator",
                "user_id": str(self.user.id),
                "username": self.user.username,
                "is_typing": True,
            }}
        )

    async def handle_typing_stop(self):
        """Handle typing indicator stop."""
        await self.channel_layer.group_send(
            self.conversation_group_name,
            {{
                "type": "typing_indicator",
                "user_id": str(self.user.id),
                "username": self.user.username,
                "is_typing": False,
            }}
        )

    async def handle_mark_read(self, data):
        """Handle mark messages as read."""
        timestamp = data.get("timestamp")
        if timestamp:
            await self.mark_messages_read(timestamp)

    async def chat_message(self, event):
        """Send chat message to WebSocket."""
        await self.send(text_data=json.dumps({{
            "type": "chat_message",
            "message": event["message"]
        }}))

    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        # Don't send typing indicator to the user who is typing
        if str(self.user.id) != event["user_id"]:
            await self.send(text_data=json.dumps({{
                "type": "typing_indicator",
                "user_id": event["user_id"],
                "username": event["username"],
                "is_typing": event["is_typing"],
            }}))

    async def send_error(self, message):
        """Send error message to WebSocket."""
        await self.send(text_data=json.dumps({{
            "type": "error",
            "message": message
        }}))

    @database_sync_to_async
    def check_participant(self):
        """Check if user is a participant in the conversation."""
        try:
            ConversationParticipant.objects.get(
                conversation_id=self.conversation_id,
                user=self.user,
                is_active=True
            )
            return True
        except ConversationParticipant.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content, message_type, reply_to_id):
        """Save message to database."""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            reply_to = None
            if reply_to_id:
                try:
                    reply_to = Message.objects.get(id=reply_to_id)
                except Message.DoesNotExist:
                    pass

            message = Message.objects.create(
                conversation=conversation,
                sender=self.user,
                content=content,
                type=message_type,
                reply_to=reply_to
            )
            return message
        except Exception as e:
            logger.error(f"Error saving message: {{e}}")
            return None

    @database_sync_to_async
    def mark_messages_read(self, timestamp):
        """Mark messages as read up to timestamp."""
        try:
            participant = ConversationParticipant.objects.get(
                conversation_id=self.conversation_id,
                user=self.user
            )
            from datetime import datetime
            participant.mark_as_read(datetime.fromisoformat(timestamp))
        except Exception as e:
            logger.error(f"Error marking messages as read: {{e}}")


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for user notifications."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.user_group_name = f"user_{{self.user.id}}"

        # Join user group
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

    async def notification(self, event):
        """Send notification to WebSocket."""
        await self.send(text_data=json.dumps({{
            "type": "notification",
            "data": event["data"]
        }}))


class OrganizationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for organization-wide notifications."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.organization_id = self.scope["url_route"]["kwargs"]["organization_id"]
        self.organization_group_name = f"org_{{self.organization_id}}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        # Check if user is a member of the organization
        is_member = await self.check_organization_member()
        if not is_member:
            await self.close()
            return

        # Join organization group
        await self.channel_layer.group_add(
            self.organization_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(
            self.organization_group_name,
            self.channel_name
        )

    async def organization_notification(self, event):
        """Send organization notification to WebSocket."""
        await self.send(text_data=json.dumps({{
            "type": "organization_notification",
            "data": event["data"]
        }}))

    @database_sync_to_async
    def check_organization_member(self):
        """Check if user is a member of the organization."""
        try:
            from {app_name}.models import OrganizationMember
            OrganizationMember.objects.get(
                organization_id=self.organization_id,
                user=self.user,
                status="active"
            )
            return True
        except OrganizationMember.DoesNotExist:
            return False
'''

CHAT_ROUTING_TEMPLATE = '''"""WebSocket routing for chat."""

from django.urls import re_path
from {app_name} import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<conversation_id>\\w+)/$", consumers.ChatConsumer.as_asgi()),
    re_path(r"ws/notifications/$", consumers.NotificationConsumer.as_asgi()),
    re_path(r"ws/organizations/(?P<organization_id>\\w+)/$", consumers.OrganizationConsumer.as_asgi()),
]
'''
