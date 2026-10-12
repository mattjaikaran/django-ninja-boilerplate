"""Notification feature generator."""

from .base_generator import BaseGenerator, GeneratorError
from .codegen import from_import, import_block, method_def, package_init

NOTIFICATION_MODELS = '''"""Notification models."""

from django.conf import settings
from django.db import models

from core.models import AbstractBaseModel


class NotificationTemplate(AbstractBaseModel):
    """Template for notifications."""

    TYPE_CHOICES = [
        ("email", "Email"),
        ("push", "Push Notification"),
        ("sms", "SMS"),
        ("in_app", "In-App Notification"),
    ]

    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    subject_template = models.CharField(max_length=255, blank=True)
    content_template = models.TextField()

    class Meta:
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"

    def __str__(self):
        return f"{self.name} ({self.type})"


class Notification(AbstractBaseModel):
    """Individual notification instance."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
        ("read", "Read"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    subject = models.CharField(max_length=255)
    content = models.TextField()
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="normal"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Delivery tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Additional context data
    context_data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} -> {self.recipient}"


class NotificationPreference(AbstractBaseModel):
    """User notification preferences."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )

    # Email preferences
    email_enabled = models.BooleanField(default=True)
    email_marketing = models.BooleanField(default=False)
    email_updates = models.BooleanField(default=True)

    # Push notification preferences
    push_enabled = models.BooleanField(default=True)
    push_marketing = models.BooleanField(default=False)

    # SMS preferences
    sms_enabled = models.BooleanField(default=False)
    sms_marketing = models.BooleanField(default=False)

    # In-app preferences
    in_app_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"{self.user} preferences"
'''

NOTIFICATION_SCHEMAS = '''"""Notification schemas."""

from datetime import datetime
from uuid import UUID

from core.schemas.base_schema import CamelCaseSchema


class NotificationSchema(CamelCaseSchema):
    id: UUID
    subject: str
    content: str
    priority: str
    status: str
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    created_at: datetime
    template_name: str

    @staticmethod
    def resolve_template_name(obj) -> str:
        """Return the name of the template the notification came from."""
        return obj.template.name


class NotificationCountSchema(CamelCaseSchema):
    total: int
    unread: int
    read: int


class NotificationPreferenceSchema(CamelCaseSchema):
    email_enabled: bool
    email_marketing: bool
    email_updates: bool
    push_enabled: bool
    push_marketing: bool
    sms_enabled: bool
    sms_marketing: bool
    in_app_enabled: bool


class UpdateNotificationPreferenceSchema(CamelCaseSchema):
    email_enabled: bool | None = None
    email_marketing: bool | None = None
    email_updates: bool | None = None
    push_enabled: bool | None = None
    push_marketing: bool | None = None
    sms_enabled: bool | None = None
    sms_marketing: bool | None = None
    in_app_enabled: bool | None = None
'''

NOTIFICATION_SCHEMA_NAMES = (
    "NotificationCountSchema",
    "NotificationPreferenceSchema",
    "NotificationSchema",
    "UpdateNotificationPreferenceSchema",
)

# Every inbox query filters on the recipient, so another user's notification
# is a 404. The controller never touches the ORM.
NOTIFICATION_SERVICE = '''"""Notification service. Every inbox query is scoped to the recipient."""

import logging
from typing import Any
from uuid import UUID

from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.template import Context, Template
from django.utils import timezone

{first_party_imports}

logger = logging.getLogger(__name__)

UNREAD_STATUSES = ("pending", "sent", "delivered")


class NotificationService:
    """Send notifications and manage the recipient's inbox and preferences."""

    def list_for_user(
        self, user: Any, *, unread_only: bool = False
    ) -> QuerySet[Notification]:
        """Return the user's notifications, newest first."""
        notifications = (
            Notification.objects.filter(recipient=user)
            .select_related("template")
            .order_by("-created_at")
        )
        if unread_only:
            notifications = notifications.filter(status__in=UNREAD_STATUSES)
        return notifications

    def get_for_user(self, notification_id: UUID, user: Any) -> Notification:
        """Return one notification sent to the user. Raise Http404 for any other."""
        return get_object_or_404(
            Notification.objects.select_related("template"),
            id=notification_id,
            recipient=user,
        )

    def get_counts(self, user: Any) -> dict[str, int]:
        """Return the total, unread and read counts for the user."""
        notifications = Notification.objects.filter(recipient=user)
        total = notifications.count()
        unread = notifications.filter(status__in=UNREAD_STATUSES).count()
        return {{"total": total, "unread": unread, "read": total - unread}}

    def mark_as_read(self, notification_id: UUID, user: Any) -> Notification:
        """Mark one of the user's notifications as read."""
        notification = self.get_for_user(notification_id, user)
        if notification.status != "read":
            notification.status = "read"
            notification.read_at = timezone.now()
            notification.save(update_fields=["status", "read_at", "updated_at"])
        return notification

    def mark_all_as_read(self, user: Any) -> dict[str, int]:
        """Mark every unread notification of the user as read. Return the counts."""
        now = timezone.now()
        Notification.objects.filter(recipient=user, status__in=UNREAD_STATUSES).update(
            status="read", read_at=now, updated_at=now
        )
        return self.get_counts(user)

    def delete(self, notification_id: UUID, user: Any) -> None:
        """Delete one of the user's notifications."""
        self.get_for_user(notification_id, user).delete()

    def get_preferences(self, user: Any) -> NotificationPreference:
        """Return the user's preferences. Create the defaults on first use."""
        preferences, _ = NotificationPreference.objects.get_or_create(user=user)
        return preferences

    def update_preferences(
        self, user: Any, payload: UpdateNotificationPreferenceSchema
    ) -> NotificationPreference:
        """Apply the set fields of the payload to the user's preferences."""
        preferences = self.get_preferences(user)
        for field in payload.model_fields_set:
            setattr(preferences, field, getattr(payload, field))
        preferences.save()
        return preferences

    def send_notification(
        self,
        recipient: Any,
        template_name: str,
        context_data: dict[str, Any] | None = None,
        priority: str = "normal",
    ) -> Notification | None:
        """Render a template for the recipient and deliver it.

        Return None when the recipient turned off the template's channel.
        """
        template = NotificationTemplate.objects.get(name=template_name, is_active=True)
        if not self._channel_enabled(template.type, self.get_preferences(recipient)):
            logger.info(
                "Notification channel %s is off for user %s",
                template.type,
                recipient.pk,
            )
            return None

        context = Context(context_data or {{}})
        notification = Notification.objects.create(
            recipient=recipient,
            template=template,
            subject=Template(template.subject_template).render(context),
            content=Template(template.content_template).render(context),
            priority=priority,
            context_data=context_data or {{}},
        )
        self._deliver(notification)
        return notification

    def _channel_enabled(
        self, channel: str, preferences: NotificationPreference
    ) -> bool:
        """Return whether the user allows notifications on the channel."""
        return {{
            "email": preferences.email_enabled,
            "push": preferences.push_enabled,
            "sms": preferences.sms_enabled,
            "in_app": preferences.in_app_enabled,
        }}[channel]

    def _deliver(self, notification: Notification) -> None:
        """Send the notification on its channel and record the outcome."""
        senders = {{
            "email": self._send_email,
            "push": self._send_push,
            "sms": self._send_sms,
            "in_app": self._send_in_app,
        }}
        try:
            senders[notification.template.type](notification)
        except Exception as error:
            notification.status = "failed"
            notification.failed_at = timezone.now()
            notification.error_message = str(error)
            notification.save(
                update_fields=["status", "failed_at", "error_message", "updated_at"]
            )
            logger.exception("Failed to send notification %s", notification.id)
            return
        notification.status = "sent"
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_at", "updated_at"])

    def _send_email(self, notification: Notification) -> None:
        """Send the notification by email."""
        from core.services.email import default_email_service

        sent = default_email_service.send_simple_email(
            subject=notification.subject,
            message=notification.content,
            recipient_email=notification.recipient.email,
        )
        if not sent:
            msg = "The email backend did not send the notification"
            raise RuntimeError(msg)

    def _send_push(self, notification: Notification) -> None:
        """Fail: this project has no push provider. Add one here to enable push."""
        msg = "No push notification provider is configured"
        raise ImproperlyConfigured(msg)

    def _send_sms(self, notification: Notification) -> None:
        """Fail: this project has no SMS provider. Add one here to enable SMS."""
        msg = "No SMS provider is configured"
        raise ImproperlyConfigured(msg)

    def _send_in_app(self, notification: Notification) -> None:
        """Publish the notification to the recipient's Centrifugo channel."""
        from api.centrifugo import centrifugo_client

        centrifugo_client.publish(
            f"notifications:{{notification.recipient_id}}",
            {{
                "type": "notification",
                "data": {{
                    "id": str(notification.id),
                    "subject": notification.subject,
                    "content": notification.content,
                    "priority": notification.priority,
                    "created_at": notification.created_at.isoformat(),
                }},
            }},
        )
'''

# AGENTS.md section 08: JWTAuth on the controller, a thin handler per route
# that calls the recipient-scoped service, and static paths before every
# /{notification_id} handler.
NOTIFICATION_CONTROLLER = '''"""Notification controller. The service scopes every route to request.user."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_put
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/notifications", tags=["Notifications"], auth=JWTAuth())
class NotificationController:
    """Inbox and preference endpoints for the authenticated user.

    Put static paths before the first /{{notification_id}} handler.
    """

    def __init__(self):
        self.service = NotificationService()

    @http_get("/", response={{200: list[NotificationSchema]}})
    @log_api_call()
    def list_notifications(self, request):
        """List the user's notifications."""
        return 200, self.service.list_for_user(request.user)

    @http_get("/unread", response={{200: list[NotificationSchema]}})
    @log_api_call()
    def list_unread_notifications(self, request):
        """List the user's unread notifications."""
        return 200, self.service.list_for_user(request.user, unread_only=True)

    @http_get("/count", response={{200: NotificationCountSchema}})
    @log_api_call()
    def get_notification_count(self, request):
        """Get the user's total, unread and read counts."""
        return 200, self.service.get_counts(request.user)

    @http_put("/mark-all-read", response={{200: NotificationCountSchema}})
    @log_api_call()
    def mark_all_as_read(self, request):
        """Mark all of the user's notifications as read. Return the new counts."""
        return 200, self.service.mark_all_as_read(request.user)

    @http_get("/preferences", response={{200: NotificationPreferenceSchema}})
    @log_api_call()
    def get_preferences(self, request):
        """Get the user's notification preferences."""
        return 200, self.service.get_preferences(request.user)

    @http_put("/preferences", response={{200: NotificationPreferenceSchema}})
    @log_api_call(include_payload=True)
{update_preferences_def}
        """Update the user's notification preferences."""
        return 200, self.service.update_preferences(request.user, payload)

    @http_put("/{{notification_id}}/read", response={{200: NotificationSchema, 404: dict}})
    @log_api_call()
    def mark_as_read(self, request, notification_id: UUID):
        """Mark one of the user's notifications as read."""
        return 200, self.service.mark_as_read(notification_id, request.user)

    @http_delete("/{{notification_id}}", response={{204: None, 404: dict}})
    @log_api_call()
    def delete_notification(self, request, notification_id: UUID):
        """Delete one of the user's notifications."""
        self.service.delete(notification_id, request.user)
        return 204, None
'''

NOTIFICATION_ADMIN = '''"""Notification admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin

{first_party_imports}


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(ModelAdmin):
    list_display = ["name", "type", "is_active", "created_at"]
    list_filter = ["type", "is_active", "created_at"]
    search_fields = ["name", "subject_template", "content_template"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = [
        "subject",
        "recipient",
        "priority",
        "status",
        "sent_at",
        "created_at",
    ]
    list_filter = ["priority", "status", "template__type", "created_at"]
    search_fields = ["subject", "content", "recipient__username", "recipient__email"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "sent_at",
        "delivered_at",
        "read_at",
        "failed_at",
    ]
    date_hierarchy = "created_at"


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(ModelAdmin):
    list_display = [
        "user",
        "email_enabled",
        "push_enabled",
        "sms_enabled",
        "in_app_enabled",
    ]
    list_filter = ["email_enabled", "push_enabled", "sms_enabled", "in_app_enabled"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
'''

# Smoke, permission and contract tests only.
NOTIFICATION_TESTS = '''"""Smoke and permission tests for the {app_name} API."""

import pytest

{first_party_imports}


def _notification(recipient, subject):
    template, _ = NotificationTemplate.objects.get_or_create(
        name="welcome", defaults={{"type": "in_app", "content_template": "Hello"}}
    )
    return Notification.objects.create(
        recipient=recipient, template=template, subject=subject, content="Hello"
    )


@pytest.mark.django_db
class TestNotificationAPI:
    """Recipient scoping, validation and the auth boundary."""

    def test_list_as_owner_returns_only_own(self, authenticated_client):
        client, user = authenticated_client
        mine = _notification(user, "Mine")
        _notification(UserFactory(), "Theirs")
        response = client.get("/api/notifications/")
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [str(mine.id)]

    def test_other_user_cannot_mark_as_read(self, authenticated_client):
        client, _ = authenticated_client
        notification = _notification(UserFactory(), "Theirs")
        response = client.put(f"/api/notifications/{{notification.id}}/read")
        assert response.status_code == 404
        notification.refresh_from_db()
        assert notification.status == "pending"

    def test_other_user_cannot_delete(self, authenticated_client):
        client, _ = authenticated_client
        notification = _notification(UserFactory(), "Theirs")
        response = client.delete(f"/api/notifications/{{notification.id}}")
        assert response.status_code == 404
        assert Notification.objects.filter(id=notification.id).exists()

    def test_update_preferences_with_invalid_payload_returns_422(
        self, authenticated_client
    ):
        client, _ = authenticated_client
        response = client.put(
            "/api/notifications/preferences",
            {{"emailEnabled": "not-a-bool"}},
            content_type="application/json",
        )
        assert_validation_error(response, field="emailEnabled")

    def test_anonymous_request_returns_401(self, api_client):
        response = api_client.get("/api/notifications/")
        assert response.status_code == 401
'''


class NotificationGenerator(BaseGenerator):
    """Generator for notification system feature."""

    def __init__(
        self,
        app_name: str = "notifications",
        minimal: bool = False,
    ):
        """Initialize the notification generator."""
        super().__init__(app_name, minimal)

    def generate(self) -> None:
        """Generate the notification feature."""
        if self.app_path.exists():
            msg = f"App '{self.app_name}' already exists"
            raise GeneratorError(msg)

        print("Generating notification system feature...")
        self.create_django_app()
        self.remove_scaffold()
        self._generate_models()
        self._generate_schemas()
        self._generate_services()
        self._generate_controllers()
        self._generate_admin()
        self._generate_tests()
        self.update_settings(self.app_name, {})
        self.update_urls(self.app_name, "NotificationController")
        self.create_migration()
        print("Notification system feature generated successfully!")

    def _app_import(self, module: str, *names: str) -> str:
        """Return ``from <app>.<module> import names`` for this app."""
        return from_import(f"{self.app_name}.{module}", *names)

    def _generate_models(self) -> None:
        """Generate notification models."""
        models_path = self.app_path / "models"
        self.create_file(models_path / "notification.py", NOTIFICATION_MODELS)
        self.create_file(
            models_path / "__init__.py",
            package_init(
                (
                    f"{self.app_name}.models.notification",
                    ["Notification", "NotificationPreference", "NotificationTemplate"],
                )
            ),
        )

    def _generate_schemas(self) -> None:
        """Generate notification schemas."""
        schemas_path = self.app_path / "schemas"
        self.create_file(schemas_path / "notification_schema.py", NOTIFICATION_SCHEMAS)
        self.create_file(
            schemas_path / "__init__.py",
            package_init(
                (
                    f"{self.app_name}.schemas.notification_schema",
                    list(NOTIFICATION_SCHEMA_NAMES),
                )
            ),
        )

    def _generate_services(self) -> None:
        """Generate the recipient-scoped notification service."""
        services_path = self.app_path / "services"
        first_party_imports = import_block(
            self._app_import(
                "models",
                "Notification",
                "NotificationPreference",
                "NotificationTemplate",
            ),
            self._app_import("schemas", "UpdateNotificationPreferenceSchema"),
        )
        self.create_file(
            services_path / "notification_service.py",
            NOTIFICATION_SERVICE.format(first_party_imports=first_party_imports),
        )
        self.create_file(
            services_path / "__init__.py",
            package_init(
                (
                    f"{self.app_name}.services.notification_service",
                    ["NotificationService"],
                )
            ),
        )

    def _generate_controllers(self) -> None:
        """Generate the notification controller."""
        controllers_path = self.app_path / "controllers"
        first_party_imports = import_block(
            "from api.decorators import log_api_call",
            self._app_import("schemas", *NOTIFICATION_SCHEMA_NAMES),
            self._app_import("services", "NotificationService"),
        )
        self.create_file(
            controllers_path / "notification_controller.py",
            NOTIFICATION_CONTROLLER.format(
                first_party_imports=first_party_imports,
                update_preferences_def=method_def(
                    "update_preferences",
                    "self, request, payload: UpdateNotificationPreferenceSchema",
                ),
            ),
        )
        self.create_file(
            controllers_path / "__init__.py",
            package_init(
                (
                    f"{self.app_name}.controllers.notification_controller",
                    ["NotificationController"],
                )
            ),
        )

    def _generate_admin(self) -> None:
        """Generate notification admin."""
        admin_path = self.app_path / "admin"
        self.create_file(
            admin_path / "notification_admin.py",
            NOTIFICATION_ADMIN.format(
                first_party_imports=self._app_import(
                    "models",
                    "Notification",
                    "NotificationPreference",
                    "NotificationTemplate",
                )
            ),
        )
        self.create_file(
            admin_path / "__init__.py",
            package_init(
                (
                    f"{self.app_name}.admin.notification_admin",
                    [
                        "NotificationAdmin",
                        "NotificationPreferenceAdmin",
                        "NotificationTemplateAdmin",
                    ],
                )
            ),
        )

    def _generate_tests(self) -> None:
        """Generate the notification smoke and permission tests."""
        first_party_imports = import_block(
            "from core.tests.factories import UserFactory",
            self._app_import("models", "Notification", "NotificationTemplate"),
            "from tests.utils.assertions import assert_validation_error",
        )
        self.create_file(
            self.app_path / "tests" / "test_notification.py",
            NOTIFICATION_TESTS.format(
                app_name=self.app_name, first_party_imports=first_party_imports
            ),
        )
