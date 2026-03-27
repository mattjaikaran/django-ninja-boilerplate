"""Notification feature generator."""

from .base_generator import BaseGenerator


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
        print("Generating notification system feature...")

        # Create Django app
        self.create_django_app()

        # Update dependencies
        self._update_dependencies()

        # Generate models
        self._generate_models()

        # Generate schemas
        self._generate_schemas()

        # Generate services
        self._generate_services()

        # Generate controllers
        self._generate_controllers()

        # Generate admin
        self._generate_admin()

        # Update settings
        self._update_settings()

        # Update URLs
        self.update_urls(self.app_name)

        # Create migrations
        self.create_migration()

        print("Notification system feature generated successfully!")

    def _update_dependencies(self) -> None:
        """Update project dependencies."""
        dependencies = []
        if not self.minimal:
            dependencies.extend(
                [
                    "firebase-admin>=6.0.0",
                ]
            )
        self.update_pyproject_toml(dependencies)

    def _generate_models(self) -> None:
        """Generate notification models."""
        models_content = '''"""Notification models."""

from django.db import models
from django.conf import settings
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
    is_active = models.BooleanField(default=True)

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
        related_name="notifications"
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    subject = models.CharField(max_length=255)
    content = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")
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
        return f"{self.subject} -> {self.recipient.username}"

    @property
    def is_read(self):
        return self.status == "read"

    def mark_as_read(self):
        if self.status != "read":
            self.status = "read"
            self.read_at = timezone.now()
            self.save()


class NotificationPreference(AbstractBaseModel):
    """User notification preferences."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences"
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
        return f"{self.user.username} preferences"
'''

        self.create_file(self.app_path / "models" / "notification.py", models_content)

        # Update models __init__.py
        init_content = """from .notification import Notification, NotificationTemplate, NotificationPreference

__all__ = ["Notification", "NotificationTemplate", "NotificationPreference"]
"""
        self.create_file(self.app_path / "models" / "__init__.py", init_content)

    def _generate_schemas(self) -> None:
        """Generate notification schemas."""
        schemas_content = '''"""Notification schemas."""

from core.schemas.base_schema import CamelCaseSchema
from typing import Optional, List


class NotificationSchema(CamelCaseSchema):
    id: str
    subject: str
    content: str
    priority: str
    status: str
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    read_at: Optional[str] = None
    created_at: str
    template_name: str


class CreateNotificationSchema(CamelCaseSchema):
    recipient_id: str
    template_name: str
    context_data: dict = {}
    priority: str = "normal"


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
    email_enabled: Optional[bool] = None
    email_marketing: Optional[bool] = None
    email_updates: Optional[bool] = None
    push_enabled: Optional[bool] = None
    push_marketing: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    sms_marketing: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
'''

        self.create_file(
            self.app_path / "schemas" / "notification_schema.py", schemas_content
        )

    def _generate_services(self) -> None:
        """Generate notification services."""
        service_content = '''"""Notification service."""

import logging
from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.template import Template, Context
from django.utils import timezone

from .models import Notification, NotificationTemplate, NotificationPreference

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications."""

    def send_notification(
        self,
        recipient: User,
        template_name: str,
        context_data: Dict[str, Any] = None,
        priority: str = "normal"
    ) -> Notification:
        """Send a notification using a template."""
        try:
            template = NotificationTemplate.objects.get(name=template_name, is_active=True)
        except NotificationTemplate.DoesNotExist:
            logger.error(f"Notification template '{template_name}' not found")
            raise

        # Get user preferences
        preferences, _ = NotificationPreference.objects.get_or_create(user=recipient)

        # Check if user has enabled this notification type
        if not self._is_notification_enabled(template.type, preferences):
            logger.info(f"Notification type '{template.type}' disabled for user {recipient.username}")
            return None

        # Render template content
        context = Context(context_data or {})
        subject = Template(template.subject_template).render(context) if template.subject_template else ""
        content = Template(template.content_template).render(context)

        # Create notification
        notification = Notification.objects.create(
            recipient=recipient,
            template=template,
            subject=subject,
            content=content,
            priority=priority,
            context_data=context_data or {}
        )

        # Send notification based on type
        self._send_by_type(notification)

        return notification

    def _is_notification_enabled(self, notification_type: str, preferences: NotificationPreference) -> bool:
        """Check if notification type is enabled for user."""
        type_enabled_map = {
            "email": preferences.email_enabled,
            "push": preferences.push_enabled,
            "sms": preferences.sms_enabled,
            "in_app": preferences.in_app_enabled,
        }
        return type_enabled_map.get(notification_type, True)

    def _send_by_type(self, notification: Notification) -> None:
        """Send notification based on its type."""
        try:
            if notification.template.type == "email":
                self._send_email(notification)
            elif notification.template.type == "push":
                self._send_push(notification)
            elif notification.template.type == "sms":
                self._send_sms(notification)
            elif notification.template.type == "in_app":
                self._send_in_app(notification)

            notification.status = "sent"
            notification.sent_at = timezone.now()
            notification.save()

        except Exception as e:
            notification.status = "failed"
            notification.failed_at = timezone.now()
            notification.error_message = str(e)
            notification.save()
            logger.error(f"Failed to send notification {notification.id}: {e}")

    def _send_email(self, notification: Notification) -> None:
        """Send email notification."""
        # Integration with email service
        from core.services.email import default_email_service

        default_email_service.send_simple_email(
            subject=notification.subject,
            message=notification.content,
            recipient_email=notification.recipient.email
        )

    def _send_push(self, notification: Notification) -> None:
        """Send push notification."""
        # TODO: Implement push notification via Firebase/etc
        logger.info(f"Push notification sent to {notification.recipient.username}")

    def _send_sms(self, notification: Notification) -> None:
        """Send SMS notification."""
        # TODO: Implement SMS via Twilio/etc
        logger.info(f"SMS notification sent to {notification.recipient.username}")

    def _send_in_app(self, notification: Notification) -> None:
        """Send in-app notification via Centrifugo."""
        from api.centrifugo import centrifugo_client

        channel = f"notifications:{notification.recipient.id}"
        centrifugo_client.publish(channel, {
            "type": "notification",
            "data": {
                "id": str(notification.id),
                "subject": notification.subject,
                "content": notification.content,
                "priority": notification.priority,
                "created_at": notification.created_at.isoformat(),
            },
        })
        logger.info(f"In-app notification sent to {notification.recipient.username}")

    def mark_as_read(self, notification_id: str, user: User) -> bool:
        """Mark notification as read."""
        try:
            notification = Notification.objects.get(id=notification_id, recipient=user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False

    def get_unread_count(self, user: User) -> int:
        """Get count of unread notifications for user."""
        return Notification.objects.filter(
            recipient=user,
            status__in=["pending", "sent", "delivered"]
        ).count()


# Global notification service instance
notification_service = NotificationService()
'''

        self.create_file(
            self.app_path / "services" / "__init__.py", "# Notification services"
        )
        self.create_file(
            self.app_path / "services" / "notification_service.py", service_content
        )

    def _generate_controllers(self) -> None:
        """Generate notification controllers."""
        controller_content = f'''"""Notification controllers."""

import logging
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import (
    create_endpoint,
    delete_endpoint,
    detail_endpoint,
    list_endpoint,
    update_endpoint,
)
from {self.app_name}.models import Notification, NotificationPreference
from {self.app_name}.schemas.notification_schema import (
    NotificationSchema,
    CreateNotificationSchema,
    NotificationPreferenceSchema,
    UpdateNotificationPreferenceSchema,
)
from {self.app_name}.services.notification_service import notification_service

logger = logging.getLogger(__name__)


@api_controller("/notifications", tags=["Notifications"])
class NotificationController:
    """Notification management controller."""

    @list_endpoint(cache_timeout=60)
    @http_get("/", response={{200: list[NotificationSchema]}})
    def list_notifications(self, request):
        """List user's notifications."""
        notifications = Notification.objects.filter(recipient=request.user).order_by("-created_at")
        return 200, notifications

    @list_endpoint(cache_timeout=60)
    @http_get("/unread", response={{200: list[NotificationSchema]}})
    def list_unread_notifications(self, request):
        """List user's unread notifications."""
        notifications = Notification.objects.filter(
            recipient=request.user,
            status__in=["pending", "sent", "delivered"]
        ).order_by("-created_at")
        return 200, notifications

    @detail_endpoint()
    @http_get("/count", response={{200: dict}})
    def get_notification_count(self, request):
        """Get notification counts."""
        total = Notification.objects.filter(recipient=request.user).count()
        unread = notification_service.get_unread_count(request.user)

        return 200, {{
            "total": total,
            "unread": unread,
            "read": total - unread
        }}

    @update_endpoint()
    @http_put("/{{str:notification_id}}/read", response={{200: dict}})
    def mark_as_read(self, request, notification_id: str):
        """Mark notification as read."""
        success = notification_service.mark_as_read(notification_id, request.user)
        if success:
            return 200, {{"message": "Notification marked as read"}}
        else:
            return 404, {{"error": "Notification not found"}}

    @update_endpoint()
    @http_put("/mark-all-read", response={{200: dict}})
    def mark_all_as_read(self, request):
        """Mark all notifications as read."""
        count = Notification.objects.filter(
            recipient=request.user,
            status__in=["pending", "sent", "delivered"]
        ).update(status="read")

        return 200, {{"message": f"Marked {{count}} notifications as read"}}

    @detail_endpoint()
    @http_get("/preferences", response={{200: NotificationPreferenceSchema}})
    def get_preferences(self, request):
        """Get user's notification preferences."""
        preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return 200, preferences

    @update_endpoint()
    @http_put("/preferences", response={{200: NotificationPreferenceSchema}})
    def update_preferences(self, request, payload: UpdateNotificationPreferenceSchema):
        """Update user's notification preferences."""
        preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)

        for key, value in payload.dict(exclude_unset=True).items():
            setattr(preferences, key, value)
        preferences.save()

        return 200, preferences

    @delete_endpoint()
    @http_delete("/{{str:notification_id}}", response={{204: dict, 404: dict}})
    def delete_notification(self, request, notification_id: str):
        """Delete a notification."""
        notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notification.delete()
        return 204, {{"message": "Notification deleted successfully"}}
'''

        self.create_file(
            self.app_path / "controllers" / "notification_controller.py",
            controller_content,
        )

    def _generate_admin(self) -> None:
        """Generate notification admin."""
        admin_content = f'''"""Notification admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin
from {self.app_name}.models import Notification, NotificationTemplate, NotificationPreference


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(ModelAdmin):
    list_display = ["name", "type", "is_active", "created_at"]
    list_filter = ["type", "is_active", "created_at"]
    search_fields = ["name", "subject_template", "content_template"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ["subject", "recipient", "priority", "status", "sent_at", "created_at"]
    list_filter = ["priority", "status", "template__type", "created_at"]
    search_fields = ["subject", "content", "recipient__username", "recipient__email"]
    readonly_fields = ["created_at", "updated_at", "sent_at", "delivered_at", "read_at", "failed_at"]
    date_hierarchy = "created_at"


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(ModelAdmin):
    list_display = ["user", "email_enabled", "push_enabled", "sms_enabled", "in_app_enabled"]
    list_filter = ["email_enabled", "push_enabled", "sms_enabled", "in_app_enabled"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
'''

        self.create_file(
            self.app_path / "admin" / "notification_admin.py", admin_content
        )

    def _update_settings(self) -> None:
        """Update Django settings for notifications."""
        settings_updates = {
            "NOTIFICATION_MAX_PER_USER": 1000 if not self.minimal else 100,
            "NOTIFICATION_CLEANUP_DAYS": 90,
            "NOTIFICATION_BATCH_SIZE": 100,
        }
        self.update_settings(self.app_name, settings_updates)
