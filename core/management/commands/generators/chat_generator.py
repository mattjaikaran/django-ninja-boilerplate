"""Chat/messaging feature generator."""

from .base_generator import BaseGenerator


class ChatGenerator(BaseGenerator):
    """Generator for chat/messaging feature."""

    def __init__(
        self,
        app_name: str = "chat",
        minimal: bool = False,
        realtime: bool = False,
    ):
        """Initialize the chat generator.

        Args:
            app_name: Name of the Django app to create
            minimal: Whether to generate minimal version
            realtime: Whether to include WebSocket support for real-time messaging
        """
        super().__init__(app_name, minimal)
        self.realtime = realtime

    def generate(self) -> None:
        """Generate the chat feature."""
        chat_type = "real-time" if self.realtime else "RESTful"
        print(f"Generating {chat_type} chat/messaging feature...")

        # Create Django app
        self.create_django_app()

        # Update dependencies
        self._update_dependencies()

        # Generate models
        self._generate_models()

        # Generate schemas
        self._generate_schemas()

        # Generate controllers
        self._generate_controllers()

        if self.realtime:
            # Generate WebSocket consumers
            self._generate_consumers()

            # Generate routing for WebSockets
            self._generate_routing()

        # Generate admin
        self._generate_admin()

        # Generate tests
        self._generate_tests()

        # Update settings
        self._update_settings()

        # Update URLs
        self.update_urls(self.app_name)

        # Create migrations
        self.create_migration()

        print(f"{chat_type.title()} chat feature generated successfully!")
        if not self.realtime:
            print(
                "Tip: Use --realtime flag to generate WebSocket support for real-time messaging."
            )

    def _update_dependencies(self) -> None:
        """Update project dependencies."""
        dependencies = []

        if self.realtime:
            dependencies.extend(
                [
                    "channels>=4.0.0",
                    "channels-redis>=4.1.0",
                    "django-cors-headers>=4.0.0",
                ]
            )

        if not self.minimal:
            dependencies.extend(
                [
                    "pillow>=10.0.0",  # For file uploads
                    "django-storages>=1.14.0",  # For cloud storage
                ]
            )

        self.update_pyproject_toml(dependencies)

    def _generate_models(self) -> None:
        """Generate chat models."""
        from .templates.model_templates import CHAT_MODELS_TEMPLATE

        self.create_file(self.app_path / "models" / "chat.py", CHAT_MODELS_TEMPLATE)

        # Update models __init__.py
        init_content = """from .chat import Conversation, ConversationParticipant, Message, MessageReaction

__all__ = ["Conversation", "ConversationParticipant", "Message", "MessageReaction"]
"""
        self.create_file(self.app_path / "models" / "__init__.py", init_content)

    def _generate_schemas(self) -> None:
        """Generate chat schemas."""
        from .templates.schema_templates import CHAT_SCHEMAS_TEMPLATE

        self.create_file(
            self.app_path / "schemas" / "chat_schema.py", CHAT_SCHEMAS_TEMPLATE
        )

    def _generate_controllers(self) -> None:
        """Generate chat controllers."""
        controllers_content = f'''"""Chat controllers."""

import logging
from uuid import UUID
from typing import List

from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Prefetch
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import (
    create_endpoint,
    delete_endpoint,
    detail_endpoint,
    list_endpoint,
    update_endpoint,
)
from {self.app_name}.models import Conversation, ConversationParticipant, Message, MessageReaction
from {self.app_name}.schemas.chat_schema import (
    ConversationSchema,
    ConversationListSchema,
    CreateConversationSchema,
    UpdateConversationSchema,
    MessageSchema,
    CreateMessageSchema,
    UpdateMessageSchema,
    AddParticipantSchema,
    UpdateParticipantSchema,
    MessageReactionSchema,
    AddReactionSchema,
)

User = get_user_model()
logger = logging.getLogger(__name__)


@api_controller("/conversations", tags=["Chat"])
class ConversationController:
    """Conversation management controller."""

    @list_endpoint(cache_timeout=60)
    @http_get("/", response={{200: List[ConversationListSchema]}})
    def list_conversations(self, request):
        """List user's conversations."""
        user = request.user

        # Get conversations where user is an active participant
        conversations = Conversation.objects.filter(
            participants__user=user,
            participants__is_active=True,
            is_active=True
        ).select_related("created_by").prefetch_related(
            Prefetch(
                "participants",
                queryset=ConversationParticipant.objects.filter(user=user),
                to_attr="user_participation"
            ),
            Prefetch(
                "messages",
                queryset=Message.objects.filter(is_active=True).order_by("-created_at")[:1],
                to_attr="latest_message"
            )
        ).distinct().order_by("-last_message_at")

        # Build response with unread counts and preview
        result = []
        for conversation in conversations:
            user_participant = conversation.user_participation[0] if conversation.user_participation else None
            latest_message = conversation.latest_message[0] if conversation.latest_message else None

            result.append({{
                "id": str(conversation.id),
                "title": conversation.title or f"Chat with {{conversation.participant_count}} people",
                "type": conversation.type,
                "participant_count": conversation.participant_count,
                "unread_count": user_participant.unread_count if user_participant else 0,
                "last_message_at": conversation.last_message_at,
                "last_message_preview": latest_message.content[:100] if latest_message else None,
            }})

        return 200, result

    @create_endpoint()
    @http_post("/", response={{201: ConversationSchema}})
    def create_conversation(self, request, payload: CreateConversationSchema):
        """Create a new conversation."""
        user = request.user

        # Create conversation
        conversation = Conversation.objects.create(
            title=payload.title,
            type=payload.type,
            description=payload.description,
            created_by=user
        )

        # Add creator as admin
        conversation.add_participant(user, added_by=user)
        creator_participant = conversation.participants.get(user=user)
        creator_participant.role = "admin"
        creator_participant.save()

        # Add other participants
        for user_id in payload.participant_user_ids:
            try:
                participant_user = User.objects.get(id=user_id)
                conversation.add_participant(participant_user, added_by=user)
            except User.DoesNotExist:
                logger.warning(f"User {{user_id}} not found when creating conversation")

        # Reload with relationships
        conversation = Conversation.objects.select_related("created_by").prefetch_related(
            "participants__user",
            "messages"
        ).get(id=conversation.id)

        return 201, conversation

    @detail_endpoint()
    @http_get("/{{str:conversation_id}}", response={{200: ConversationSchema, 404: dict}})
    def get_conversation(self, request, conversation_id: str):
        """Get conversation details with recent messages."""
        user = request.user

        # Check if user is participant
        conversation = get_object_or_404(
            Conversation.objects.select_related("created_by").prefetch_related(
                "participants__user",
                Prefetch(
                    "messages",
                    queryset=Message.objects.filter(is_active=True).select_related("sender").order_by("-created_at")[:20],
                    to_attr="recent_messages_list"
                )
            ),
            id=conversation_id,
            participants__user=user,
            participants__is_active=True
        )

        # Mark as read
        try:
            participant = conversation.participants.get(user=user)
            participant.mark_as_read()
        except ConversationParticipant.DoesNotExist:
            pass

        return 200, conversation

    @update_endpoint()
    @http_put("/{{str:conversation_id}}", response={{200: ConversationSchema, 404: dict}})
    def update_conversation(self, request, conversation_id: str, payload: UpdateConversationSchema):
        """Update conversation details."""
        user = request.user

        # Check if user is admin of the conversation
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants__user=user,
            participants__role__in=["admin", "moderator"]
        )

        # Apply updates
        for key, value in payload.dict(exclude_unset=True).items():
            setattr(conversation, key, value)
        conversation.save()

        # Reload with relationships
        conversation = Conversation.objects.select_related("created_by").prefetch_related(
            "participants__user"
        ).get(id=conversation.id)

        return 200, conversation

    @create_endpoint()
    @http_post("/{{str:conversation_id}}/participants", response={{201: dict}})
    def add_participant(self, request, conversation_id: str, payload: AddParticipantSchema):
        """Add a participant to the conversation."""
        user = request.user

        # Check if user can add participants
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            participants__user=user,
            participants__role__in=["admin", "moderator"]
        )

        # Add participant
        try:
            participant_user = User.objects.get(id=payload.user_id)
            participant = conversation.add_participant(participant_user, added_by=user)
            participant.role = payload.role
            participant.save()

            return 201, {{"message": f"{{participant_user.username}} added to conversation"}}
        except User.DoesNotExist:
            return 400, {{"error": "User not found"}}

    @delete_endpoint()
    @http_delete("/{{str:conversation_id}}/participants/{{str:user_id}}", response={{204: dict}})
    def remove_participant(self, request, conversation_id: str, user_id: str):
        """Remove a participant from the conversation."""
        user = request.user

        # Check permissions - admin/moderator can remove others, users can remove themselves
        conversation = get_object_or_404(Conversation, id=conversation_id)

        if str(user.id) == user_id:
            # User removing themselves
            success = conversation.remove_participant(user)
        else:
            # Admin/moderator removing someone else
            if not conversation.participants.filter(
                user=user,
                role__in=["admin", "moderator"]
            ).exists():
                return 403, {{"error": "Permission denied"}}

            try:
                target_user = User.objects.get(id=user_id)
                success = conversation.remove_participant(target_user)
            except User.DoesNotExist:
                return 400, {{"error": "User not found"}}

        if success:
            return 204, {{"message": "Participant removed successfully"}}
        else:
            return 400, {{"error": "Participant not found"}}


@api_controller("/messages", tags=["Chat"])
class MessageController:
    """Message management controller."""

    @list_endpoint(cache_timeout=60)
    @http_get("/conversation/{{str:conversation_id}}", response={{200: List[MessageSchema]}})
    def list_messages(self, request, conversation_id: str, offset: int = 0, limit: int = 50):
        """List messages in a conversation with pagination."""
        user = request.user

        # Check if user is participant
        get_object_or_404(
            ConversationParticipant,
            conversation_id=conversation_id,
            user=user,
            is_active=True
        )

        messages = Message.objects.filter(
            conversation_id=conversation_id,
            is_active=True
        ).select_related("sender").order_by("-created_at")[offset:offset + limit]

        return 200, list(reversed(messages))  # Reverse to show oldest first

    @create_endpoint()
    @http_post("/conversation/{{str:conversation_id}}", response={{201: MessageSchema}})
    def create_message(self, request, conversation_id: str, payload: CreateMessageSchema):
        """Send a message to a conversation."""
        user = request.user

        # Check if user is participant
        participant = get_object_or_404(
            ConversationParticipant,
            conversation_id=conversation_id,
            user=user,
            is_active=True
        )

        # Create message
        message = Message.objects.create(
            conversation_id=conversation_id,
            sender=user,
            content=payload.content,
            type=payload.type,
            reply_to_id=payload.reply_to_id,
            file_url=payload.file_url,
            file_name=payload.file_name,
            file_size=payload.file_size,
            file_type=payload.file_type,
        )

        return 201, message

    @update_endpoint()
    @http_put("/{{str:message_id}}", response={{200: MessageSchema, 404: dict}})
    def update_message(self, request, message_id: str, payload: UpdateMessageSchema):
        """Edit a message."""
        user = request.user

        message = get_object_or_404(Message, id=message_id, sender=user, is_active=True)

        message.content = payload.content
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save()

        return 200, message

    @delete_endpoint()
    @http_delete("/{{str:message_id}}", response={{204: dict}})
    def delete_message(self, request, message_id: str):
        """Delete a message."""
        user = request.user

        message = get_object_or_404(Message, id=message_id, sender=user, is_active=True)
        message.is_active = False
        message.save()

        return 204, {{"message": "Message deleted successfully"}}

    @create_endpoint()
    @http_post("/{{str:message_id}}/reactions", response={{201: MessageReactionSchema}})
    def add_reaction(self, request, message_id: str, payload: AddReactionSchema):
        """Add a reaction to a message."""
        user = request.user

        # Check if user can access this message
        message = get_object_or_404(
            Message,
            id=message_id,
            conversation__participants__user=user,
            is_active=True
        )

        reaction, created = MessageReaction.objects.get_or_create(
            message=message,
            user=user,
            emoji=payload.emoji
        )

        if created:
            return 201, reaction
        else:
            return 200, reaction

    @delete_endpoint()
    @http_delete("/{{str:message_id}}/reactions/{{str:emoji}}", response={{204: dict}})
    def remove_reaction(self, request, message_id: str, emoji: str):
        """Remove a reaction from a message."""
        user = request.user

        try:
            reaction = MessageReaction.objects.get(
                message_id=message_id,
                user=user,
                emoji=emoji
            )
            reaction.delete()
            return 204, {{"message": "Reaction removed"}}
        except MessageReaction.DoesNotExist:
            return 404, {{"error": "Reaction not found"}}
'''

        self.create_file(
            self.app_path / "controllers" / "chat_controller.py", controllers_content
        )

    def _generate_consumers(self) -> None:
        """Generate WebSocket consumers for real-time chat."""
        if not self.realtime:
            return

        from .templates.websocket_templates import CHAT_CONSUMERS_TEMPLATE

        consumers_content = CHAT_CONSUMERS_TEMPLATE.format(app_name=self.app_name)
        self.create_file(self.app_path / "consumers.py", consumers_content)

    def _generate_routing(self) -> None:
        """Generate WebSocket routing."""
        if not self.realtime:
            return

        from .templates.websocket_templates import CHAT_ROUTING_TEMPLATE

        routing_content = CHAT_ROUTING_TEMPLATE.format(app_name=self.app_name)
        self.create_file(self.app_path / "routing.py", routing_content)

    def _generate_admin(self) -> None:
        """Generate chat admin."""
        from .templates.admin_templates import CHAT_ADMIN_TEMPLATE

        admin_content = CHAT_ADMIN_TEMPLATE.format(app_name=self.app_name)
        self.create_file(self.app_path / "admin" / "chat_admin.py", admin_content)

    def _generate_tests(self) -> None:
        """Generate chat tests."""
        from .templates.test_templates import CHAT_TESTS_TEMPLATE

        tests_content = CHAT_TESTS_TEMPLATE.format(app_name=self.app_name)
        self.create_file(self.app_path / "tests" / "test_chat.py", tests_content)

    def _update_settings(self) -> None:
        """Update Django settings for chat."""
        settings_updates = {
            "CHAT_MESSAGE_MAX_LENGTH": 2000,
            "CHAT_FILE_UPLOAD_MAX_SIZE": 10 * 1024 * 1024,  # 10MB
            "CHAT_CONVERSATION_MAX_PARTICIPANTS": 100,
        }

        if self.realtime:
            settings_updates.update(
                {
                    "CHANNEL_LAYERS": {
                        "default": {
                            "BACKEND": "channels_redis.core.RedisChannelLayer",
                            "CONFIG": {
                                "hosts": [("redis", 6379)],
                            },
                        },
                    }
                }
            )

        self.update_settings(self.app_name, settings_updates)
