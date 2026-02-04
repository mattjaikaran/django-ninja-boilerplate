"""Audit Log Models.

This module defines the AuditLog model for tracking all changes
in the system for compliance and debugging purposes.
"""

import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class AuditAction(models.TextChoices):
    """Enum for audit action types."""

    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    SOFT_DELETE = "SOFT_DELETE", "Soft Delete"
    RESTORE = "RESTORE", "Restore"
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    LOGIN_FAILED = "LOGIN_FAILED", "Login Failed"
    PASSWORD_CHANGE = "PASSWORD_CHANGE", "Password Change"
    PASSWORD_RESET = "PASSWORD_RESET", "Password Reset"
    API_REQUEST = "API_REQUEST", "API Request"
    PERMISSION_CHANGE = "PERMISSION_CHANGE", "Permission Change"
    EXPORT = "EXPORT", "Export"
    IMPORT = "IMPORT", "Import"
    CUSTOM = "CUSTOM", "Custom Action"


class AuditLog(models.Model):
    """Model for storing audit trail entries.

    Tracks all significant actions in the system including:
    - Model create/update/delete operations
    - Authentication events (login, logout, password changes)
    - API requests (via middleware)
    - Custom audit actions (via decorator)

    Designed for compliance requirements (GDPR, SOC2, HIPAA, etc.)
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this audit log entry",
    )

    # Action details
    action = models.CharField(
        max_length=50,
        choices=AuditAction.choices,
        db_index=True,
        help_text="Type of action performed",
    )

    action_description = models.TextField(
        blank=True,
        default="",
        help_text="Human-readable description of the action",
    )

    # User who performed the action
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="User who performed the action",
    )

    user_email = models.EmailField(
        blank=True,
        default="",
        db_index=True,
        help_text="Email of the user (preserved even if user is deleted)",
    )

    # What was affected
    model_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Name of the model that was affected",
    )

    object_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="ID of the object that was affected",
    )

    object_repr = models.TextField(
        blank=True,
        default="",
        help_text="String representation of the object",
    )

    # Change details
    changes = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="JSON object containing the changes made",
    )

    previous_state = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="State of the object before the change",
    )

    new_state = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="State of the object after the change",
    )

    # Request context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_index=True,
        help_text="IP address of the request",
    )

    user_agent = models.TextField(
        blank=True,
        default="",
        help_text="User agent string from the request",
    )

    request_method = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="HTTP method of the request",
    )

    request_path = models.TextField(
        blank=True,
        default="",
        help_text="URL path of the request",
    )

    request_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="Unique request ID for correlation",
    )

    # Timing
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the action occurred",
    )

    # Additional context
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Additional contextual data",
    )

    # Status
    success = models.BooleanField(
        default=True,
        help_text="Whether the action was successful",
    )

    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Error message if the action failed",
    )

    class Meta:
        app_label = "core"
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["model_name", "-timestamp"]),
            models.Index(fields=["model_name", "object_id"]),
            models.Index(fields=["ip_address", "-timestamp"]),
            models.Index(fields=["request_id"]),
        ]

    def __str__(self) -> str:
        """Return string representation of the audit log entry."""
        user_str = self.user_email or "Anonymous"
        return f"{self.action} by {user_str} on {self.model_name or 'N/A'} at {self.timestamp}"

    @classmethod
    def log_action(
        cls,
        action: str,
        user=None,
        model_name: str = "",
        object_id: str = "",
        object_repr: str = "",
        changes: dict | None = None,
        previous_state: dict | None = None,
        new_state: dict | None = None,
        ip_address: str | None = None,
        user_agent: str = "",
        request_method: str = "",
        request_path: str = "",
        request_id: str = "",
        extra_data: dict | None = None,
        success: bool = True,
        error_message: str = "",
        action_description: str = "",
    ) -> "AuditLog":
        """Create an audit log entry.

        Args:
            action: Type of action (from AuditAction choices)
            user: User who performed the action
            model_name: Name of the affected model
            object_id: ID of the affected object
            object_repr: String representation of the object
            changes: Dictionary of changes made
            previous_state: State before the change
            new_state: State after the change
            ip_address: IP address of the request
            user_agent: User agent string
            request_method: HTTP method
            request_path: URL path
            request_id: Unique request identifier
            extra_data: Additional contextual data
            success: Whether the action succeeded
            error_message: Error message if failed
            action_description: Human-readable description

        Returns:
            Created AuditLog instance
        """
        user_email = ""
        if user and hasattr(user, "email"):
            user_email = user.email or ""

        return cls.objects.create(
            action=action,
            action_description=action_description,
            user=user,
            user_email=user_email,
            model_name=model_name,
            object_id=str(object_id) if object_id else "",
            object_repr=object_repr,
            changes=changes or {},
            previous_state=previous_state or {},
            new_state=new_state or {},
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
            request_id=request_id,
            extra_data=extra_data or {},
            success=success,
            error_message=error_message,
        )
