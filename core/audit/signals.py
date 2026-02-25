"""Django Signals for Audit Logging.

This module provides signal handlers to automatically track model changes.
It uses Django's pre_save and post_save signals to capture changes.
"""

import logging
from typing import Any

from django.conf import settings
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from api.utils.http import get_client_ip

logger = logging.getLogger(__name__)

# Thread-local storage for request context
import threading

_thread_locals = threading.local()


def set_audit_context(request=None, user=None) -> None:
    """Set the current request context for audit logging.

    This should be called by middleware or decorators to provide
    request context to signal handlers.

    Args:
        request: The current HTTP request
        user: The current user (optional, will be extracted from request if not provided)
    """
    _thread_locals.request = request
    if user is None and request and hasattr(request, "user"):
        _thread_locals.user = request.user if request.user.is_authenticated else None
    else:
        _thread_locals.user = user


def get_audit_context() -> tuple[Any, Any]:
    """Get the current audit context.

    Returns:
        Tuple of (request, user)
    """
    request = getattr(_thread_locals, "request", None)
    user = getattr(_thread_locals, "user", None)
    return request, user


def clear_audit_context() -> None:
    """Clear the audit context after request processing."""
    _thread_locals.request = None
    _thread_locals.user = None


def get_model_field_values(instance: models.Model) -> dict[str, Any]:
    """Extract serializable field values from a model instance.

    Args:
        instance: The model instance

    Returns:
        Dictionary of field names to values
    """
    data = {}
    for field in instance._meta.get_fields():
        if not hasattr(field, "name"):
            continue

        field_name = field.name

        # Skip reverse relations
        if field.is_relation and not field.concrete:
            continue

        # Skip many-to-many for now (complex to serialize)
        if field.many_to_many:
            continue

        try:
            value = getattr(instance, field_name, None)

            # Convert special types to serializable format
            if value is not None and hasattr(value, "pk"):
                value = str(value.pk)
            elif value is not None and hasattr(value, "isoformat"):
                value = value.isoformat()
            elif isinstance(value, bytes):
                value = "[binary data]"
            elif not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                value = str(value)

            # Mask sensitive fields
            if field_name.lower() in (
                "password",
                "token",
                "secret",
                "api_key",
                "apikey",
            ):
                value = "[REDACTED]"

            data[field_name] = value
        except Exception:
            # Skip fields that can't be serialized
            pass

    return data


def calculate_changes(
    old_values: dict[str, Any], new_values: dict[str, Any]
) -> dict[str, Any]:
    """Calculate the differences between old and new field values.

    Args:
        old_values: Previous field values
        new_values: New field values

    Returns:
        Dictionary mapping field names to {"old": value, "new": value}
    """
    changes = {}

    # Get all field names from both dictionaries
    all_fields = set(old_values.keys()) | set(new_values.keys())

    for field in all_fields:
        old_value = old_values.get(field)
        new_value = new_values.get(field)

        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}

    return changes


# Models to track - can be configured in settings
# Default to tracking all models except AuditLog itself
def get_tracked_models() -> list[str] | None:
    """Get list of model names to track.

    Returns:
        List of model names to track, or None for all models
    """
    return getattr(settings, "AUDIT_TRACKED_MODELS", None)


def get_excluded_models() -> list[str]:
    """Get list of model names to exclude from tracking.

    Returns:
        List of model names to exclude
    """
    default_excluded = [
        "AuditLog",
        "Session",
        "ContentType",
        "Permission",
        "LogEntry",
        "MigrationHistory",
        "Migration",
    ]
    return getattr(settings, "AUDIT_EXCLUDED_MODELS", default_excluded)


def should_track_model(model_name: str) -> bool:
    """Determine if a model should be tracked.

    Args:
        model_name: Name of the model class

    Returns:
        True if the model should be tracked
    """
    tracked = get_tracked_models()
    excluded = get_excluded_models()

    if model_name in excluded:
        return False

    if tracked is None:
        return True

    return model_name in tracked


# Store pre-save state for calculating changes
_pre_save_state = {}


@receiver(pre_save)
def audit_pre_save(sender, instance, **kwargs):
    """Capture model state before save for change tracking.

    Args:
        sender: The model class
        instance: The model instance being saved
        **kwargs: Additional signal arguments
    """
    model_name = sender.__name__

    if not should_track_model(model_name):
        return

    # Store the instance's primary key
    pk = instance.pk

    # For existing instances, capture current database state
    if pk:
        try:
            # Get the current database state
            current = sender.objects.filter(pk=pk).first()
            if current:
                _pre_save_state[f"{model_name}:{pk}"] = get_model_field_values(current)
        except Exception as e:
            logger.debug("Could not capture pre-save state: %s", e)


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    """Log model changes after save.

    Args:
        sender: The model class
        instance: The model instance that was saved
        created: True if a new instance was created
        **kwargs: Additional signal arguments
    """
    # Import here to avoid circular imports
    from core.audit.models import AuditAction, AuditLog

    model_name = sender.__name__

    if not should_track_model(model_name):
        return

    # Get audit context
    request, user = get_audit_context()

    # Extract request metadata
    ip_address = None
    user_agent = ""
    request_id = ""

    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        request_id = getattr(request, "audit_request_id", "")

    # Get the new state
    new_state = get_model_field_values(instance)

    # Determine action and calculate changes
    pk = str(instance.pk)
    state_key = f"{model_name}:{pk}"

    if created:
        action = AuditAction.CREATE
        previous_state = {}
        changes = {}
        action_description = f"Created {model_name}"
    else:
        # Check if this is a soft delete or restore
        is_active_changed = False
        old_is_active = None
        new_is_active = new_state.get("is_active")

        previous_state = _pre_save_state.pop(state_key, {})
        old_is_active = previous_state.get("is_active")

        if old_is_active is not None and new_is_active is not None:
            is_active_changed = old_is_active != new_is_active

        if is_active_changed:
            if new_is_active:
                action = AuditAction.RESTORE
                action_description = f"Restored {model_name}"
            else:
                action = AuditAction.SOFT_DELETE
                action_description = f"Soft deleted {model_name}"
        else:
            action = AuditAction.UPDATE
            action_description = f"Updated {model_name}"

        changes = calculate_changes(previous_state, new_state)

    # Don't log if no changes (except for creates)
    if not created and not changes:
        return

    # Create audit log
    try:
        AuditLog.log_action(
            action=action,
            action_description=action_description,
            user=user,
            model_name=model_name,
            object_id=pk,
            object_repr=str(instance)[:200],
            changes=changes,
            previous_state=previous_state,
            new_state=new_state,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
    except Exception as e:
        logger.exception("Failed to create audit log for save: %s", e)


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    """Log model deletions (hard delete).

    Args:
        sender: The model class
        instance: The model instance that was deleted
        **kwargs: Additional signal arguments
    """
    # Import here to avoid circular imports
    from core.audit.models import AuditAction, AuditLog

    model_name = sender.__name__

    if not should_track_model(model_name):
        return

    # Get audit context
    request, user = get_audit_context()

    # Extract request metadata
    ip_address = None
    user_agent = ""
    request_id = ""

    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        request_id = getattr(request, "audit_request_id", "")

    # Capture the deleted state
    deleted_state = get_model_field_values(instance)

    try:
        AuditLog.log_action(
            action=AuditAction.DELETE,
            action_description=f"Deleted {model_name}",
            user=user,
            model_name=model_name,
            object_id=str(instance.pk),
            object_repr=str(instance)[:200],
            previous_state=deleted_state,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
    except Exception as e:
        logger.exception("Failed to create audit log for delete: %s", e)


@receiver(user_logged_in)
def audit_user_login(sender, request, user, **kwargs):
    """Log successful user logins.

    Args:
        sender: The sender class
        request: The HTTP request
        user: The user who logged in
        **kwargs: Additional signal arguments
    """
    from core.audit.models import AuditAction, AuditLog

    ip_address = get_client_ip(request) if request else None
    user_agent = request.META.get("HTTP_USER_AGENT", "") if request else ""
    request_id = getattr(request, "audit_request_id", "") if request else ""

    try:
        AuditLog.log_action(
            action=AuditAction.LOGIN,
            action_description=f"User {user.email} logged in",
            user=user,
            model_name="User",
            object_id=str(user.pk),
            object_repr=str(user),
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
    except Exception as e:
        logger.exception("Failed to log user login: %s", e)


@receiver(user_logged_out)
def audit_user_logout(sender, request, user, **kwargs):
    """Log user logouts.

    Args:
        sender: The sender class
        request: The HTTP request
        user: The user who logged out
        **kwargs: Additional signal arguments
    """
    from core.audit.models import AuditAction, AuditLog

    if user is None:
        return

    ip_address = get_client_ip(request) if request else None
    user_agent = request.META.get("HTTP_USER_AGENT", "") if request else ""
    request_id = getattr(request, "audit_request_id", "") if request else ""

    try:
        AuditLog.log_action(
            action=AuditAction.LOGOUT,
            action_description=f"User {user.email} logged out",
            user=user,
            model_name="User",
            object_id=str(user.pk),
            object_repr=str(user),
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
    except Exception as e:
        logger.exception("Failed to log user logout: %s", e)


@receiver(user_login_failed)
def audit_user_login_failed(sender, credentials, request, **kwargs):
    """Log failed login attempts.

    Args:
        sender: The sender class
        credentials: The credentials that were used
        request: The HTTP request
        **kwargs: Additional signal arguments
    """
    from core.audit.models import AuditAction, AuditLog

    ip_address = get_client_ip(request) if request else None
    user_agent = request.META.get("HTTP_USER_AGENT", "") if request else ""
    request_id = getattr(request, "audit_request_id", "") if request else ""

    # Get the attempted username/email (mask most of it)
    attempted_user = credentials.get("username", credentials.get("email", "unknown"))
    if "@" in attempted_user and len(attempted_user) > 5:
        # Mask email: show first 2 chars and domain
        parts = attempted_user.split("@")
        attempted_user = f"{parts[0][:2]}***@{parts[1]}"
    elif len(attempted_user) > 3:
        attempted_user = f"{attempted_user[:2]}***"

    try:
        AuditLog.log_action(
            action=AuditAction.LOGIN_FAILED,
            action_description=f"Failed login attempt for {attempted_user}",
            user=None,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            success=False,
            error_message="Invalid credentials",
            extra_data={"attempted_user": attempted_user},
        )
    except Exception as e:
        logger.exception("Failed to log failed login: %s", e)


def setup_audit_signals():
    """Initialize audit signal handlers.

    This function is called from AppConfig.ready() to ensure
    signals are connected when the app starts.
    """
    # Signals are connected automatically via @receiver decorators
    # This function exists for explicit initialization if needed
    logger.info("Audit logging signals initialized")
