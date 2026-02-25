"""Model templates for code generation."""

MODEL_TEMPLATE = '''"""{app_name} models."""

from django.db import models
from core.models import AbstractBaseModel


class {model_name}(AbstractBaseModel):
    """{model_name} model."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "{model_name}"
        verbose_name_plural = "{app_name_title}"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
'''

RBAC_MODELS_TEMPLATE = '''"""RBAC models."""

from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from core.models import AbstractBaseModel


class Permission(AbstractBaseModel):
    """Permission model for fine-grained access control."""

    name = models.CharField(max_length=255, unique=True)
    codename = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The content type this permission applies to"
    )

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Role(AbstractBaseModel):
    """Role model for grouping permissions."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission,
        through="RolePermission",
        related_name="roles"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this role is assigned to new users by default"
    )

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RolePermission(AbstractBaseModel):
    """Through model for Role-Permission relationship."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ["role", "permission"]
        verbose_name = "Role Permission"
        verbose_name_plural = "Role Permissions"


class UserRole(AbstractBaseModel):
    """User-Role assignment with optional object-level scope."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_roles"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    # Optional object-level permissions
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Content type for object-level permissions"
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Object ID for object-level permissions"
    )
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        unique_together = ["user", "role", "content_type", "object_id"]
        verbose_name = "User Role"
        verbose_name_plural = "User Roles"

    def __str__(self):
        if self.content_object:
            return f"{self.user.username} - {self.role.name} on {self.content_object}"
        return f"{self.user.username} - {self.role.name}"

    @property
    def is_global(self):
        """Check if this is a global role assignment."""
        return self.content_type is None and self.object_id is None
'''

CHAT_MODELS_TEMPLATE = '''"""Chat models."""

from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import AbstractBaseModel


class Conversation(AbstractBaseModel):
    """A conversation between multiple participants."""

    CONVERSATION_TYPES = [
        ("private", "Private Chat"),
        ("group", "Group Chat"),
        ("channel", "Channel"),
    ]

    title = models.CharField(max_length=255, blank=True)
    type = models.CharField(max_length=20, choices=CONVERSATION_TYPES, default="private")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_conversations"
    )
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ["-last_message_at", "-created_at"]

    def __str__(self):
        if self.title:
            return self.title
        return f"{self.get_type_display()} - {self.created_at.strftime('%Y-%m-%d')}"

    @property
    def participant_count(self):
        return self.participants.filter(is_active=True).count()

    def add_participant(self, user, added_by=None):
        """Add a participant to the conversation."""
        participant, created = ConversationParticipant.objects.get_or_create(
            conversation=self,
            user=user,
            defaults={
                "added_by": added_by,
                "joined_at": timezone.now(),
            }
        )
        if not created and not participant.is_active:
            participant.is_active = True
            participant.joined_at = timezone.now()
            participant.save()
        return participant

    def remove_participant(self, user):
        """Remove a participant from the conversation."""
        try:
            participant = self.participants.get(user=user)
            participant.is_active = False
            participant.left_at = timezone.now()
            participant.save()
            return True
        except ConversationParticipant.DoesNotExist:
            return False


class ConversationParticipant(AbstractBaseModel):
    """A participant in a conversation."""

    PARTICIPANT_ROLES = [
        ("member", "Member"),
        ("admin", "Admin"),
        ("moderator", "Moderator"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_participations"
    )
    role = models.CharField(max_length=20, choices=PARTICIPANT_ROLES, default="member")
    is_active = models.BooleanField(default=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_participants"
    )
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    last_read_at = models.DateTimeField(default=timezone.now)
    notifications_enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ["conversation", "user"]
        verbose_name = "Conversation Participant"
        verbose_name_plural = "Conversation Participants"

    def __str__(self):
        return f"{self.user.username} in {self.conversation}"

    @property
    def unread_count(self):
        """Get count of unread messages for this participant."""
        return self.conversation.messages.filter(
            created_at__gt=self.last_read_at,
            is_active=True
        ).exclude(sender=self.user).count()

    def mark_as_read(self, timestamp=None):
        """Mark messages as read up to a certain timestamp."""
        if timestamp is None:
            timestamp = timezone.now()
        self.last_read_at = timestamp
        self.save(update_fields=["last_read_at"])

    @property
    def is_admin(self):
        return self.role in ["admin"]

    @property
    def can_invite(self):
        return self.role in ["admin", "moderator"]


class Message(AbstractBaseModel):
    """A message in a conversation."""

    MESSAGE_TYPES = [
        ("text", "Text"),
        ("image", "Image"),
        ("file", "File"),
        ("system", "System"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )
    content = models.TextField()
    type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default="text")
    is_active = models.BooleanField(default=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    # Reply functionality
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies"
    )

    # File attachments
    file_url = models.URLField(blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    file_type = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender", "created_at"]),
        ]

    def __str__(self):
        return f"Message from {self.sender.username} in {self.conversation}"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)

        # Update conversation's last_message_at
        if is_new:
            self.conversation.last_message_at = self.created_at
            self.conversation.save(update_fields=["last_message_at"])


class MessageReaction(AbstractBaseModel):
    """A reaction to a message."""

    REACTION_TYPES = [
        ("👍", "Thumbs Up"),
        ("👎", "Thumbs Down"),
        ("❤️", "Heart"),
        ("😂", "Laugh"),
        ("😮", "Wow"),
        ("😢", "Sad"),
        ("😡", "Angry"),
    ]

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_reactions"
    )
    emoji = models.CharField(max_length=10, choices=REACTION_TYPES)

    class Meta:
        unique_together = ["message", "user", "emoji"]
        verbose_name = "Message Reaction"
        verbose_name_plural = "Message Reactions"

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to message"
'''

ORGANIZATION_MODELS_TEMPLATE = '''"""Organization models."""

from django.db import models
from django.conf import settings
from django.utils import timezone
from core.models import AbstractBaseModel


class Organization(AbstractBaseModel):
    """Organization/Company model with enhanced structure."""

    # Basic info
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)

    # Contact info
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Address
    address = models.JSONField(default=dict, blank=True, help_text="JSON structure for flexible address storage")

    # Business info
    tax_id = models.CharField(max_length=50, blank=True, db_index=True)
    industry = models.CharField(max_length=100, blank=True)
    size = models.CharField(
        max_length=20,
        choices=[
            ("startup", "Startup (1-10)"),
            ("small", "Small (11-50)"),
            ("medium", "Medium (51-200)"),
            ("large", "Large (201-1000)"),
            ("enterprise", "Enterprise (1000+)"),
        ],
        default="startup"
    )

    # Status and settings
    is_active = models.BooleanField(default=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    settings = models.JSONField(default=dict, blank=True)

    # Billing
    billing_email = models.EmailField(blank=True)
    subscription_tier = models.CharField(
        max_length=20,
        choices=[
            ("free", "Free"),
            ("basic", "Basic"),
            ("pro", "Professional"),
            ("enterprise", "Enterprise"),
        ],
        default="free"
    )

    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name", "is_active"]),
            models.Index(fields=["slug", "is_active"]),
            models.Index(fields=["industry", "size"]),
        ]

    def __str__(self):
        return self.name

    @property
    def active_member_count(self):
        """Get count of active members."""
        return self.members.filter(status="active").count()

    @property
    def admin_count(self):
        """Get count of admin members."""
        return self.members.filter(status="active", role__in=["owner", "admin"]).count()

    def add_member(self, user, role="member", invited_by=None):
        """Add a member to the organization."""
        member, created = OrganizationMember.objects.get_or_create(
            organization=self,
            user=user,
            defaults={
                "role": role,
                "invited_by": invited_by,
                "invited_at": timezone.now(),
                "status": "active" if invited_by else "pending",
            }
        )
        if not created and member.status != "active":
            member.status = "active"
            member.joined_at = timezone.now()
            member.save()
        return member

    def remove_member(self, user):
        """Remove a member from the organization."""
        try:
            member = self.members.get(user=user)
            member.status = "inactive"
            member.save()
            return True
        except OrganizationMember.DoesNotExist:
            return False


class OrganizationMember(AbstractBaseModel):
    """Enhanced organization membership model."""

    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Administrator"),
        ("manager", "Manager"),
        ("member", "Member"),
        ("viewer", "Viewer"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Pending Invitation"),
        ("suspended", "Suspended"),
        ("inactive", "Inactive"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Invitation tracking
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_invitations_sent"
    )
    invited_at = models.DateTimeField(null=True, blank=True)
    invitation_token = models.CharField(max_length=255, blank=True, unique=True)
    invitation_expires_at = models.DateTimeField(null=True, blank=True)

    # Membership tracking
    joined_at = models.DateTimeField(null=True, blank=True)
    last_active_at = models.DateTimeField(auto_now=True)

    # Settings
    permissions = models.JSONField(default=dict, blank=True)
    notification_preferences = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ["organization", "user"]
        verbose_name = "Organization Member"
        verbose_name_plural = "Organization Members"
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["role", "status"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.organization.name} ({self.role})"

    @property
    def is_admin(self):
        return self.role in ["owner", "admin"]

    @property
    def can_invite(self):
        return self.role in ["owner", "admin", "manager"]

    @property
    def can_manage_members(self):
        return self.role in ["owner", "admin"]

    @property
    def is_owner(self):
        return self.role == "owner"

    def has_permission(self, permission_key):
        """Check if member has a specific permission."""
        if self.is_owner:
            return True
        return self.permissions.get(permission_key, False)

    def grant_permission(self, permission_key):
        """Grant a permission to the member."""
        if not self.permissions:
            self.permissions = {}
        self.permissions[permission_key] = True
        self.save(update_fields=["permissions"])

    def revoke_permission(self, permission_key):
        """Revoke a permission from the member."""
        if self.permissions and permission_key in self.permissions:
            self.permissions[permission_key] = False
            self.save(update_fields=["permissions"])
'''
