"""Templates for the chat feature generator.

Each template is verbatim code. ``fill_imports`` puts the first-party imports,
which depend on the app name, where ``{first_party_imports}`` stands.
"""

from core.management.commands.generators.codegen import (
    fill_imports,
    from_import,
    package_init,
)

CHAT_MODELS_TEMPLATE = '''"""Chat models: conversations, participants, messages and reactions."""

from django.conf import settings
from django.db import models
from django.utils import timezone

{first_party_imports}


class Conversation(AbstractBaseModel):
    """A conversation between participants. ``created_by`` comes from the base."""

    TYPE_CHOICES = [
        ("private", "Private chat"),
        ("group", "Group chat"),
        ("channel", "Channel"),
    ]

    title = models.CharField(max_length=255, blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="private")
    description = models.TextField(blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_message_at", "-created_at"]

    def __str__(self) -> str:
        return self.title or f"{self.get_type_display()} {self.id}"


class ConversationParticipant(AbstractBaseModel):
    """A user in a conversation. ``is_active`` is False after the user leaves."""

    ROLE_CHOICES = [
        ("member", "Member"),
        ("admin", "Admin"),
        ("moderator", "Moderator"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_participations",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    last_read_at = models.DateTimeField(default=timezone.now)
    notifications_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = [("conversation", "user")]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.conversation_id}"


class Message(AbstractBaseModel):
    """A message in a conversation. ``is_active`` is False after deletion."""

    TYPE_CHOICES = [
        ("text", "Text"),
        ("image", "Image"),
        ("file", "File"),
        ("system", "System"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_sent_messages",
    )
    content = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="text")
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    file_url = models.URLField(blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    file_type = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Message {self.id} in {self.conversation_id}"


class MessageReaction(AbstractBaseModel):
    """One emoji reaction by one user on one message."""

    EMOJI_CHOICES = [
        ("thumbs_up", "Thumbs up"),
        ("thumbs_down", "Thumbs down"),
        ("heart", "Heart"),
        ("laugh", "Laugh"),
        ("wow", "Wow"),
        ("sad", "Sad"),
        ("angry", "Angry"),
    ]

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_reactions",
    )
    emoji = models.CharField(max_length=20, choices=EMOJI_CHOICES)

    class Meta:
        unique_together = [("message", "user", "emoji")]

    def __str__(self) -> str:
        return f"{self.emoji} on {self.message_id}"
'''

CHAT_SCHEMAS_TEMPLATE = '''"""Chat schemas. Choice values match the chat models."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from django.conf import settings
from pydantic import BeforeValidator, Field

{first_party_imports}

# Serialize UUID primary and foreign keys as strings.
UUIDStr = Annotated[str, BeforeValidator(str)]
ConversationType = Literal["private", "group", "channel"]
ParticipantRole = Literal["member", "admin", "moderator"]
MessageType = Literal["text", "image", "file", "system"]
ReactionEmoji = Literal[
    "thumbs_up", "thumbs_down", "heart", "laugh", "wow", "sad", "angry"
]


class ParticipantSchema(CamelCaseSchema):
    id: UUIDStr
    user_id: UUIDStr
    username: str
    role: ParticipantRole
    joined_at: datetime
    last_read_at: datetime

    @staticmethod
    def resolve_username(obj) -> str:
        return obj.user.username


class ConversationListSchema(CamelCaseSchema):
    id: UUIDStr
    title: str
    type: ConversationType
    participant_count: int
    unread_count: int
    last_message_at: datetime | None = None


class ConversationSchema(CamelCaseSchema):
    id: UUIDStr
    title: str
    type: ConversationType
    description: str
    created_by_id: UUIDStr | None = None
    participant_count: int
    last_message_at: datetime | None = None
    created_at: datetime
    participants: list[ParticipantSchema]


class CreateConversationSchema(CamelCaseSchema):
    title: str = Field("", max_length=255)
    type: ConversationType = "private"
    description: str = ""
    participant_user_ids: list[UUID] = Field(
        default_factory=list, max_length=settings.CHAT_CONVERSATION_MAX_PARTICIPANTS
    )


class UpdateConversationSchema(CamelCaseSchema):
    title: str | None = Field(None, max_length=255)
    description: str | None = None


class AddParticipantSchema(CamelCaseSchema):
    user_id: UUID
    role: ParticipantRole = "member"


class MessageSchema(CamelCaseSchema):
    id: UUIDStr
    conversation_id: UUIDStr
    sender_id: UUIDStr
    content: str
    type: MessageType
    is_edited: bool
    reply_to_id: UUIDStr | None = None
    file_url: str
    file_name: str
    file_size: int | None = None
    file_type: str
    created_at: datetime
    edited_at: datetime | None = None


class CreateMessageSchema(CamelCaseSchema):
    content: str = Field(..., min_length=1, max_length=settings.CHAT_MESSAGE_MAX_LENGTH)
    type: MessageType = "text"
    reply_to_id: UUID | None = None
    file_url: str = Field("", max_length=200)
    file_name: str = Field("", max_length=255)
    file_size: int | None = Field(None, ge=0)
    file_type: str = Field("", max_length=100)


class UpdateMessageSchema(CamelCaseSchema):
    content: str = Field(..., min_length=1, max_length=settings.CHAT_MESSAGE_MAX_LENGTH)


class MessageReactionSchema(CamelCaseSchema):
    id: UUIDStr
    message_id: UUIDStr
    user_id: UUIDStr
    emoji: ReactionEmoji
    created_at: datetime


class AddReactionSchema(CamelCaseSchema):
    emoji: ReactionEmoji
'''

CONVERSATION_SERVICE_TEMPLATE = '''"""Conversation business logic. Every query is scoped to the user's participation."""

from typing import Any
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import (
    Count,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone

{first_party_imports}

User = get_user_model()

# Participant roles that can edit a conversation and manage its participants.
MANAGER_ROLES = ("admin", "moderator")


class ConversationService:
    """Conversations the user takes part in. Others are a 404."""

    def _participations(self, user: Any) -> QuerySet[ConversationParticipant]:
        """Return the user's active participations in active conversations."""
        return ConversationParticipant.objects.filter(
            user=user, is_active=True, conversation__is_active=True
        )

    def _conversations(self, user: Any) -> QuerySet[Conversation]:
        """Return the user's conversations with their active participant count."""
        return Conversation.objects.filter(
            is_active=True,
            id__in=self._participations(user).values("conversation_id"),
        ).annotate(
            participant_count=Count(
                "participants", filter=Q(participants__is_active=True)
            )
        )

    def _participation_as_manager(
        self, conversation_id: UUID, user: Any
    ) -> ConversationParticipant:
        """Return the user's participation. Raise 403 unless admin or moderator."""
        participation = get_object_or_404(
            self._participations(user).select_related("conversation"),
            conversation_id=conversation_id,
        )
        if participation.role not in MANAGER_ROLES:
            raise APIPermissionError(
                "Only conversation admins and moderators can do this"
            )
        return participation

    def list_for_user(self, user: Any) -> QuerySet[Conversation]:
        """Return the user's conversations with unread counts, newest first."""
        last_read = self._participations(user).filter(
            conversation=OuterRef(OuterRef("pk"))
        )
        unread = (
            Message.objects.filter(
                conversation=OuterRef("pk"),
                is_active=True,
                created_at__gt=Subquery(last_read.values("last_read_at")[:1]),
            )
            .exclude(sender=user)
            .order_by()
            .values("conversation")
            .annotate(total=Count("id"))
            .values("total")
        )
        return self._conversations(user).annotate(
            unread_count=Coalesce(Subquery(unread, output_field=IntegerField()), 0)
        )

    def get_for_user(self, conversation_id: UUID, user: Any) -> Conversation:
        """Return one of the user's conversations with its active participants."""
        participants = ConversationParticipant.objects.filter(
            is_active=True
        ).select_related("user")
        return get_object_or_404(
            self._conversations(user).prefetch_related(
                Prefetch("participants", queryset=participants)
            ),
            id=conversation_id,
        )

    def open_for_user(self, conversation_id: UUID, user: Any) -> Conversation:
        """Mark a conversation read for the user and return it."""
        self._participations(user).filter(conversation_id=conversation_id).update(
            last_read_at=timezone.now()
        )
        return self.get_for_user(conversation_id, user)

    def create(self, user: Any, payload: CreateConversationSchema) -> Conversation:
        """Create a conversation with the user as admin and the listed members."""
        member_ids = set(payload.participant_user_ids) - {user.pk}
        members = list(User.objects.filter(id__in=member_ids, is_active=True))
        missing = member_ids - {member.pk for member in members}
        if len(member_ids) + 1 > settings.CHAT_CONVERSATION_MAX_PARTICIPANTS:
            raise ValidationError("Too many participants")
        if missing:
            raise ValidationError(
                "Unknown participant user ids",
                details={"participantUserIds": sorted(str(pk) for pk in missing)},
            )
        with transaction.atomic():
            conversation = Conversation.objects.create(
                title=payload.title,
                type=payload.type,
                description=payload.description,
                created_by=user,
            )
            ConversationParticipant.objects.bulk_create(
                [
                    ConversationParticipant(
                        conversation=conversation, user=user, role="admin"
                    ),
                    *(
                        ConversationParticipant(conversation=conversation, user=member)
                        for member in members
                    ),
                ]
            )
        return self.get_for_user(conversation.id, user)

    def update(
        self, conversation_id: UUID, user: Any, payload: UpdateConversationSchema
    ) -> Conversation:
        """Apply the set fields of the payload. Admins and moderators only."""
        conversation = self._participation_as_manager(
            conversation_id, user
        ).conversation
        for field in payload.model_fields_set:
            value = getattr(payload, field)
            if value is not None:
                setattr(conversation, field, value)
        conversation.save()
        return self.get_for_user(conversation_id, user)

    def add_participant(
        self, conversation_id: UUID, user: Any, payload: AddParticipantSchema
    ) -> ConversationParticipant:
        """Add a user. Admins and moderators; only admins grant manager roles."""
        participation = self._participation_as_manager(conversation_id, user)
        if payload.role in MANAGER_ROLES and participation.role != "admin":
            raise APIPermissionError("Only conversation admins can grant this role")
        conversation = participation.conversation
        new_user = get_object_or_404(User, id=payload.user_id, is_active=True)
        existing = conversation.participants.filter(user=new_user).first()
        if existing is not None and existing.is_active:
            raise ConflictError("The user is already a participant")
        active_count = conversation.participants.filter(is_active=True).count()
        if active_count >= settings.CHAT_CONVERSATION_MAX_PARTICIPANTS:
            raise ValidationError("The conversation is full")
        participant, _ = ConversationParticipant.objects.update_or_create(
            conversation=conversation,
            user=new_user,
            defaults={
                "role": payload.role,
                "is_active": True,
                "joined_at": timezone.now(),
                "left_at": None,
            },
        )
        return participant

    def remove_participant(
        self, conversation_id: UUID, user_id: UUID, user: Any
    ) -> None:
        """Remove a participant. Users can leave; managers can remove others.

        Moderators can remove members only; admins can remove anyone.
        """
        participation = get_object_or_404(
            self._participations(user), conversation_id=conversation_id
        )
        if user_id != user.pk and participation.role not in MANAGER_ROLES:
            raise APIPermissionError(
                "Only conversation admins and moderators can remove others"
            )
        target = get_object_or_404(
            ConversationParticipant,
            conversation_id=conversation_id,
            user_id=user_id,
            is_active=True,
        )
        if (
            target.pk != participation.pk
            and target.role in MANAGER_ROLES
            and participation.role != "admin"
        ):
            raise APIPermissionError("Only conversation admins can remove managers")
        target.is_active = False
        target.left_at = timezone.now()
        target.save(update_fields=["is_active", "left_at", "updated_at"])
'''

MESSAGE_SERVICE_TEMPLATE = '''"""Message business logic. Every query is scoped to the user's conversations."""

from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone

{first_party_imports}


class MessageService:
    """Messages in conversations the user takes part in. Others are a 404."""

    def _conversation_ids(self, user: Any) -> QuerySet[ConversationParticipant]:
        """Return the ids of the user's active conversations."""
        return ConversationParticipant.objects.filter(
            user=user, is_active=True, conversation__is_active=True
        ).values("conversation_id")

    def _visible_messages(self, user: Any) -> QuerySet[Message]:
        """Return the active messages in the user's conversations."""
        return Message.objects.filter(
            is_active=True, conversation_id__in=self._conversation_ids(user)
        )

    def _own_message(self, message_id: UUID, user: Any) -> Message:
        """Return an active message the user sent to one of their conversations."""
        return get_object_or_404(
            self._visible_messages(user), id=message_id, sender=user
        )

    def list_for_conversation(
        self, conversation_id: UUID, user: Any
    ) -> QuerySet[Message]:
        """Return the conversation's messages, newest first."""
        get_object_or_404(
            Conversation,
            id=conversation_id,
            id__in=self._conversation_ids(user),
        )
        return (
            self._visible_messages(user)
            .filter(conversation_id=conversation_id)
            .order_by("-created_at")
        )

    def create(
        self, conversation_id: UUID, user: Any, payload: CreateMessageSchema
    ) -> Message:
        """Send a message to one of the user's conversations."""
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            id__in=self._conversation_ids(user),
        )
        if payload.reply_to_id is not None:
            get_object_or_404(
                self._visible_messages(user),
                id=payload.reply_to_id,
                conversation=conversation,
            )
        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                sender=user,
                created_by=user,
                content=payload.content,
                type=payload.type,
                reply_to_id=payload.reply_to_id,
                file_url=payload.file_url,
                file_name=payload.file_name,
                file_size=payload.file_size,
                file_type=payload.file_type,
            )
            conversation.last_message_at = message.created_at
            conversation.save(update_fields=["last_message_at", "updated_at"])
        return message

    def update(
        self, message_id: UUID, user: Any, payload: UpdateMessageSchema
    ) -> Message:
        """Edit a message the user sent."""
        message = self._own_message(message_id, user)
        message.content = payload.content
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save(update_fields=["content", "is_edited", "edited_at", "updated_at"])
        return message

    def delete(self, message_id: UUID, user: Any) -> None:
        """Soft-delete a message the user sent."""
        message = self._own_message(message_id, user)
        message.is_active = False
        message.save(update_fields=["is_active", "updated_at"])

    def add_reaction(
        self, message_id: UUID, user: Any, payload: AddReactionSchema
    ) -> tuple[MessageReaction, bool]:
        """Add the user's reaction. Return the reaction and whether it is new."""
        message = get_object_or_404(self._visible_messages(user), id=message_id)
        return MessageReaction.objects.get_or_create(
            message=message, user=user, emoji=payload.emoji
        )

    def remove_reaction(self, message_id: UUID, emoji: str, user: Any) -> None:
        """Remove one of the user's reactions."""
        get_object_or_404(
            MessageReaction,
            message_id=message_id,
            user=user,
            emoji=emoji,
            message__conversation_id__in=self._conversation_ids(user),
        ).delete()
'''

CONVERSATION_CONTROLLER_TEMPLATE = '''"""Conversation controller. The service scopes every route to request.user."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/conversations", tags=["Chat"], auth=JWTAuth())
class ConversationController:
    """Conversations the authenticated user takes part in.

    Put static paths before the first /{conversation_id} handler.
    """

    def __init__(self):
        self.service = ConversationService()

    @http_get("/", response={200: list[ConversationListSchema]})
    @log_api_call()
    def list_conversations(self, request):
        """List the user's conversations with unread counts."""
        return 200, self.service.list_for_user(request.user)

    @http_post("/", response={201: ConversationSchema, 400: dict})
    @log_api_call(include_payload=True)
    def create_conversation(self, request, payload: CreateConversationSchema):
        """Create a conversation with the user as admin."""
        return 201, self.service.create(request.user, payload)

    @http_get("/{conversation_id}", response={200: ConversationSchema, 404: dict})
    @log_api_call()
    def get_conversation(self, request, conversation_id: UUID):
        """Get one of the user's conversations and mark it read."""
        return 200, self.service.open_for_user(conversation_id, request.user)

    @http_put(
        "/{conversation_id}",
        response={200: ConversationSchema, 403: dict, 404: dict},
    )
    @log_api_call(include_payload=True)
    def update_conversation(
        self, request, conversation_id: UUID, payload: UpdateConversationSchema
    ):
        """Update a conversation. Admins and moderators only."""
        return 200, self.service.update(conversation_id, request.user, payload)

    @http_post(
        "/{conversation_id}/participants",
        response={201: ParticipantSchema, 400: dict, 403: dict, 404: dict, 409: dict},
    )
    @log_api_call(include_payload=True)
    def add_participant(
        self, request, conversation_id: UUID, payload: AddParticipantSchema
    ):
        """Add a participant. Admins and moderators only."""
        return 201, self.service.add_participant(conversation_id, request.user, payload)

    @http_delete(
        "/{conversation_id}/participants/{user_id}",
        response={204: None, 403: dict, 404: dict},
    )
    @log_api_call()
    def remove_participant(self, request, conversation_id: UUID, user_id: UUID):
        """Leave a conversation, or remove another participant as a manager."""
        self.service.remove_participant(conversation_id, user_id, request.user)
        return 204, None
'''

MESSAGE_CONTROLLER_TEMPLATE = '''"""Message controller. The service scopes every route to request.user."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_extra.pagination import PageNumberPaginationExtra, paginate
from ninja_extra.schemas import PaginatedResponseSchema
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/messages", tags=["Chat"], auth=JWTAuth())
class MessageController:
    """Messages in conversations the authenticated user takes part in.

    Put static paths before the first /{message_id} handler.
    """

    def __init__(self):
        self.service = MessageService()

    @http_get(
        "/conversation/{conversation_id}",
        response={200: PaginatedResponseSchema[MessageSchema], 404: dict},
    )
    @log_api_call()
    @paginate(PageNumberPaginationExtra)
    def list_messages(self, request, conversation_id: UUID):
        """List a conversation's messages, newest first."""
        return self.service.list_for_conversation(conversation_id, request.user)

    @http_post(
        "/conversation/{conversation_id}",
        response={201: MessageSchema, 404: dict},
    )
    @log_api_call(include_payload=True)
    def create_message(
        self, request, conversation_id: UUID, payload: CreateMessageSchema
    ):
        """Send a message to one of the user's conversations."""
        return 201, self.service.create(conversation_id, request.user, payload)

    @http_put("/{message_id}", response={200: MessageSchema, 404: dict})
    @log_api_call(include_payload=True)
    def update_message(self, request, message_id: UUID, payload: UpdateMessageSchema):
        """Edit a message the user sent."""
        return 200, self.service.update(message_id, request.user, payload)

    @http_delete("/{message_id}", response={204: None, 404: dict})
    @log_api_call()
    def delete_message(self, request, message_id: UUID):
        """Delete a message the user sent."""
        self.service.delete(message_id, request.user)
        return 204, None

    @http_post(
        "/{message_id}/reactions",
        response={200: MessageReactionSchema, 201: MessageReactionSchema, 404: dict},
    )
    @log_api_call(include_payload=True)
    def add_reaction(self, request, message_id: UUID, payload: AddReactionSchema):
        """React to a message. Return 200 when the reaction already exists."""
        reaction, created = self.service.add_reaction(message_id, request.user, payload)
        return (201 if created else 200), reaction

    @http_delete("/{message_id}/reactions/{emoji}", response={204: None, 404: dict})
    @log_api_call()
    def remove_reaction(self, request, message_id: UUID, emoji: ReactionEmoji):
        """Remove one of the user's reactions."""
        self.service.remove_reaction(message_id, emoji, request.user)
        return 204, None
'''

CHAT_ADMIN_TEMPLATE = '''"""Chat admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin

{first_party_imports}


@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = ["title", "type", "created_by", "last_message_at", "is_active"]
    list_filter = ["type", "is_active", "created_at"]
    search_fields = ["title", "description", "created_by__username"]
    readonly_fields = ["created_at", "updated_at", "last_message_at"]


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(ModelAdmin):
    list_display = ["user", "conversation", "role", "is_active", "joined_at"]
    list_filter = ["role", "is_active", "joined_at"]
    search_fields = ["user__username", "conversation__title"]
    readonly_fields = ["created_at", "updated_at", "joined_at", "left_at"]


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ["sender", "conversation", "type", "is_active", "created_at"]
    list_filter = ["type", "is_active", "is_edited", "created_at"]
    search_fields = ["content", "sender__username", "conversation__title"]
    readonly_fields = ["created_at", "updated_at", "edited_at"]


@admin.register(MessageReaction)
class MessageReactionAdmin(ModelAdmin):
    list_display = ["user", "message", "emoji", "created_at"]
    list_filter = ["emoji", "created_at"]
    search_fields = ["user__username", "message__content"]
    readonly_fields = ["created_at", "updated_at"]
'''

CHAT_TESTS_TEMPLATE = '''"""Smoke and permission tests for the chat API."""

import pytest

{first_party_imports}


def start_conversation(owner, *members):
    """Create a conversation with ``owner`` as admin through the service."""
    payload = CreateConversationSchema(
        title="Chat", participant_user_ids=[member.pk for member in members]
    )
    return ConversationService().create(owner, payload)


@pytest.mark.django_db
class TestChatAPI:
    """Smoke and permission tests for conversation and message endpoints."""

    def test_list_as_participant_returns_200(self, authenticated_client):
        client, user = authenticated_client
        conversation = start_conversation(user)
        response = client.get("/api/conversations/")
        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [str(conversation.id)]

    def test_list_requires_authentication(self, api_client):
        response = api_client.get("/api/conversations/")
        assert response.status_code == 401

    def test_non_participant_cannot_read_conversation(self, authenticated_client):
        client, _ = authenticated_client
        conversation = start_conversation(UserFactory())
        response = client.get(f"/api/conversations/{conversation.id}")
        assert response.status_code == 404

    def test_non_participant_cannot_read_messages(self, authenticated_client):
        client, _ = authenticated_client
        conversation = start_conversation(UserFactory())
        response = client.get(f"/api/messages/conversation/{conversation.id}")
        assert response.status_code == 404

    def test_member_cannot_add_participants(self, authenticated_client):
        client, user = authenticated_client
        conversation = start_conversation(UserFactory(), user)
        response = client.post(
            f"/api/conversations/{conversation.id}/participants",
            {"userId": str(UserFactory().pk)},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_moderator_cannot_grant_admin(self, authenticated_client):
        client, user = authenticated_client
        owner = UserFactory()
        conversation = start_conversation(owner)
        moderator = AddParticipantSchema(user_id=user.pk, role="moderator")
        ConversationService().add_participant(conversation.id, owner, moderator)
        response = client.post(
            f"/api/conversations/{conversation.id}/participants",
            {"userId": str(UserFactory().pk), "role": "admin"},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_create_with_invalid_type_returns_422(self, authenticated_client):
        client, _ = authenticated_client
        response = client.post(
            "/api/conversations/", {"type": "bogus"}, content_type="application/json"
        )
        assert_validation_error(response, field="type")

    def test_send_message_without_content_returns_422(self, authenticated_client):
        client, user = authenticated_client
        conversation = start_conversation(user)
        response = client.post(
            f"/api/messages/conversation/{conversation.id}",
            {},
            content_type="application/json",
        )
        assert_validation_error(response, field="content")
'''


def render_chat_files(app_name: str) -> dict[str, str]:
    """Return the generated files keyed by path relative to the app directory."""
    return {
        "models/chat.py": fill_imports(
            CHAT_MODELS_TEMPLATE,
            from_import("core.models", "AbstractBaseModel"),
        ),
        "schemas/chat_schema.py": fill_imports(
            CHAT_SCHEMAS_TEMPLATE,
            from_import("core.schemas.base_schema", "CamelCaseSchema"),
        ),
        "services/conversation_service.py": fill_imports(
            CONVERSATION_SERVICE_TEMPLATE,
            from_import(
                "api.exceptions",
                "APIPermissionError",
                "ConflictError",
                "ValidationError",
            ),
            from_import(
                f"{app_name}.models",
                "Conversation",
                "ConversationParticipant",
                "Message",
            ),
            from_import(
                f"{app_name}.schemas",
                "AddParticipantSchema",
                "CreateConversationSchema",
                "UpdateConversationSchema",
            ),
        ),
        "services/message_service.py": fill_imports(
            MESSAGE_SERVICE_TEMPLATE,
            from_import(
                f"{app_name}.models",
                "Conversation",
                "ConversationParticipant",
                "Message",
                "MessageReaction",
            ),
            from_import(
                f"{app_name}.schemas",
                "AddReactionSchema",
                "CreateMessageSchema",
                "UpdateMessageSchema",
            ),
        ),
        "controllers/conversation_controller.py": fill_imports(
            CONVERSATION_CONTROLLER_TEMPLATE,
            from_import("api.decorators", "log_api_call"),
            from_import(
                f"{app_name}.schemas",
                "AddParticipantSchema",
                "ConversationListSchema",
                "ConversationSchema",
                "CreateConversationSchema",
                "ParticipantSchema",
                "UpdateConversationSchema",
            ),
            from_import(f"{app_name}.services", "ConversationService"),
        ),
        "controllers/message_controller.py": fill_imports(
            MESSAGE_CONTROLLER_TEMPLATE,
            from_import("api.decorators", "log_api_call"),
            from_import(
                f"{app_name}.schemas",
                "AddReactionSchema",
                "CreateMessageSchema",
                "MessageReactionSchema",
                "MessageSchema",
                "ReactionEmoji",
                "UpdateMessageSchema",
            ),
            from_import(f"{app_name}.services", "MessageService"),
        ),
        "admin/chat_admin.py": fill_imports(
            CHAT_ADMIN_TEMPLATE,
            from_import(
                f"{app_name}.models",
                "Conversation",
                "ConversationParticipant",
                "Message",
                "MessageReaction",
            ),
        ),
        "tests/test_chat.py": fill_imports(
            CHAT_TESTS_TEMPLATE,
            from_import(
                f"{app_name}.schemas",
                "AddParticipantSchema",
                "CreateConversationSchema",
            ),
            from_import(f"{app_name}.services", "ConversationService"),
            from_import("core.tests.factories", "UserFactory"),
            from_import("tests.utils.assertions", "assert_validation_error"),
        ),
        "models/__init__.py": package_init(
            (
                f"{app_name}.models.chat",
                [
                    "Conversation",
                    "ConversationParticipant",
                    "Message",
                    "MessageReaction",
                ],
            )
        ),
        "schemas/__init__.py": package_init(
            (
                f"{app_name}.schemas.chat_schema",
                [
                    "AddParticipantSchema",
                    "AddReactionSchema",
                    "ConversationListSchema",
                    "ConversationSchema",
                    "CreateConversationSchema",
                    "CreateMessageSchema",
                    "MessageReactionSchema",
                    "MessageSchema",
                    "ParticipantSchema",
                    "ReactionEmoji",
                    "UpdateConversationSchema",
                    "UpdateMessageSchema",
                ],
            )
        ),
        "services/__init__.py": package_init(
            (f"{app_name}.services.conversation_service", ["ConversationService"]),
            (f"{app_name}.services.message_service", ["MessageService"]),
        ),
        "controllers/__init__.py": package_init(
            (
                f"{app_name}.controllers.conversation_controller",
                ["ConversationController"],
            ),
            (f"{app_name}.controllers.message_controller", ["MessageController"]),
        ),
        "admin/__init__.py": package_init(
            (
                f"{app_name}.admin.chat_admin",
                [
                    "ConversationAdmin",
                    "ConversationParticipantAdmin",
                    "MessageAdmin",
                    "MessageReactionAdmin",
                ],
            )
        ),
    }


# Centrifugo real-time service (api.centrifugo). Django stays WSGI; Centrifugo
# handles every WebSocket connection.
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
            centrifugo_client.publish(
                channel,
                {{
                    "type": "chat_message",
                    "message": message_data,
                }},
            )
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
            centrifugo_client.publish(
                channel,
                {{
                    "type": "typing_indicator",
                    "user_id": user_id,
                    "username": username,
                    "is_typing": is_typing,
                }},
            )
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
            centrifugo_client.publish(
                channel,
                {{
                    "type": "read_receipt",
                    "user_id": user_id,
                    "timestamp": timestamp,
                }},
            )
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
