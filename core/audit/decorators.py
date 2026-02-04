"""Audit Logging Decorators.

This module provides decorators for explicit audit logging in views and functions.
Use @audit_action when you need to log specific actions that aren't automatically
captured by signals (e.g., complex business logic, external API calls).
"""

import functools
import logging
from collections.abc import Callable
from typing import Any

from core.audit.middleware import get_client_ip
from core.audit.signals import set_audit_context

logger = logging.getLogger(__name__)


def audit_action(
    action: str,
    action_description: str = "",
    model_name: str = "",
    include_request_data: bool = False,
    log_result: bool = False,
    get_object_id: Callable[..., str] | None = None,
    get_extra_data: Callable[..., dict] | None = None,
):
    """Decorator to explicitly log an audit action.

    Use this decorator when you need to log actions that aren't automatically
    captured by Django signals, such as:
    - Complex business logic operations
    - External API calls
    - Bulk operations
    - Administrative actions

    Args:
        action: The action type (use AuditAction constants)
        action_description: Human-readable description of the action
        model_name: Name of the model affected (if applicable)
        include_request_data: Include sanitized request data in extra_data
        log_result: Include function result in extra_data
        get_object_id: Callable that extracts object_id from function args
        get_extra_data: Callable that extracts extra_data from function args

    Example:
        @audit_action(
            action=AuditAction.CUSTOM,
            action_description="Processed bulk payment",
            model_name="Payment",
            get_object_id=lambda *args, **kwargs: kwargs.get('payment_id'),
            get_extra_data=lambda *args, **kwargs: {'amount': kwargs.get('amount')}
        )
        def process_bulk_payment(self, request, payment_id, amount):
            # ... payment processing logic
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            from core.audit.models import AuditLog

            # Try to extract request from args
            request = None
            user = None

            # Check for request in various positions
            # For class methods, request is often args[1] (after self)
            # For function views, request is args[0]
            for arg in args:
                if hasattr(arg, "META") and hasattr(arg, "user"):
                    request = arg
                    if hasattr(request, "user") and request.user.is_authenticated:
                        user = request.user
                    break

            # Also check kwargs
            if request is None:
                request = kwargs.get("request")
                if (
                    request
                    and hasattr(request, "user")
                    and request.user.is_authenticated
                ):
                    user = request.user

            # Set audit context for any nested signal handlers
            if request:
                set_audit_context(request, user)

            # Extract request metadata
            ip_address = None
            user_agent = ""
            request_id = ""
            request_method = ""
            request_path = ""

            if request:
                ip_address = get_client_ip(request)
                user_agent = request.META.get("HTTP_USER_AGENT", "")
                request_id = getattr(request, "audit_request_id", "")
                request_method = request.method
                request_path = request.path

            # Extract object_id if callback provided
            object_id = ""
            if get_object_id:
                try:
                    object_id = str(get_object_id(*args, **kwargs))
                except Exception as e:
                    logger.debug("Could not extract object_id: %s", e)

            # Extract extra_data if callback provided
            extra_data = {}
            if get_extra_data:
                try:
                    extra_data = get_extra_data(*args, **kwargs) or {}
                except Exception as e:
                    logger.debug("Could not extract extra_data: %s", e)

            # Include sanitized request data if requested
            if include_request_data and request:
                try:
                    if hasattr(request, "data"):
                        # Ninja/REST framework request
                        request_data = dict(request.data) if request.data else {}
                    elif request.POST:
                        request_data = dict(request.POST)
                    else:
                        request_data = {}

                    # Remove sensitive fields
                    sensitive_fields = [
                        "password",
                        "token",
                        "secret",
                        "api_key",
                        "apikey",
                        "authorization",
                    ]
                    for field in sensitive_fields:
                        if field in request_data:
                            request_data[field] = "[REDACTED]"

                    extra_data["request_data"] = request_data
                except Exception as e:
                    logger.debug("Could not extract request data: %s", e)

            # Execute the function
            success = True
            error_message = ""
            result = None

            try:
                result = func(*args, **kwargs)
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                # Log the result if requested
                if log_result and success and result is not None:
                    try:
                        # Try to serialize the result
                        if hasattr(result, "model_dump"):
                            extra_data["result"] = result.model_dump()
                        elif isinstance(result, (dict, list, str, int, float, bool)):
                            extra_data["result"] = result
                        else:
                            extra_data["result"] = str(result)[:500]
                    except Exception:
                        extra_data["result"] = "[unserializable]"

                # Create the audit log entry
                try:
                    AuditLog.log_action(
                        action=action,
                        action_description=action_description
                        or f"Executed {func.__name__}",
                        user=user,
                        model_name=model_name,
                        object_id=object_id,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        request_method=request_method,
                        request_path=request_path,
                        request_id=request_id,
                        extra_data=extra_data,
                        success=success,
                        error_message=error_message,
                    )
                except Exception as e:
                    # Don't let audit logging failures break the function
                    logger.exception("Failed to create audit log: %s", e)

            return result

        return wrapper

    return decorator


def audit_context_middleware(get_response):
    """Middleware to set audit context for signal handlers.

    This middleware ensures that the request context is available
    to Django signal handlers for audit logging.

    Add this to MIDDLEWARE in settings.py, before AuditLoggingMiddleware.
    """

    def middleware(request):
        # Set the audit context
        user = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user

        set_audit_context(request, user)

        try:
            response = get_response(request)
        finally:
            # Clear the context after the request
            from core.audit.signals import clear_audit_context

            clear_audit_context()

        return response

    return middleware


class AuditContextMiddleware:
    """Class-based middleware for setting audit context.

    This is an alternative to the function-based middleware above.
    Use whichever style matches your project's conventions.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set the audit context
        user = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user

        set_audit_context(request, user)

        try:
            response = self.get_response(request)
        finally:
            # Clear the context after the request
            from core.audit.signals import clear_audit_context

            clear_audit_context()

        return response
