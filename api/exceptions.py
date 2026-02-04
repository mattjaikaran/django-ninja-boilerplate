"""Custom exceptions for the django-ninja-boilerplate API.

This module contains all custom exceptions used throughout the application
to provide better error handling and more descriptive error messages.
"""

import logging
from typing import Any

from django.http import JsonResponse
from ninja.errors import HttpError

logger = logging.getLogger(__name__)


class BaseAPIException(Exception):
    """Base exception class for all API exceptions."""

    default_message = "An error occurred"
    default_code = "api_error"
    status_code = 500

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        result = {
            "error": True,
            "message": self.message,
            "code": self.code,
        }
        if self.details:
            result["details"] = self.details
        return result


class ValidationError(BaseAPIException):
    """Raised when validation fails."""

    default_message = "Validation failed"
    default_code = "validation_error"
    status_code = 400


class AuthenticationError(BaseAPIException):
    """Raised when authentication fails."""

    default_message = "Authentication required"
    default_code = "authentication_error"
    status_code = 401


class APIPermissionError(BaseAPIException):
    """Raised when user doesn't have required permissions."""

    default_message = "Permission denied"
    default_code = "permission_error"
    status_code = 403


class NotFoundError(BaseAPIException):
    """Raised when a resource is not found."""

    default_message = "Resource not found"
    default_code = "not_found"
    status_code = 404


class ConflictError(BaseAPIException):
    """Raised when there's a conflict with current state."""

    default_message = "Conflict with current state"
    default_code = "conflict_error"
    status_code = 409


class RateLimitError(BaseAPIException):
    """Raised when rate limit is exceeded."""

    default_message = "Rate limit exceeded"
    default_code = "rate_limit_exceeded"
    status_code = 429


class ExternalServiceError(BaseAPIException):
    """Raised when an external service fails."""

    default_message = "External service error"
    default_code = "external_service_error"
    status_code = 502


# Business Logic Exceptions


class UserError(BaseAPIException):
    """Raised when user operations fail."""

    default_message = "User operation failed"
    default_code = "user_error"
    status_code = 422


class TodoError(BaseAPIException):
    """Raised when todo operations fail."""

    default_message = "Todo operation failed"
    default_code = "todo_error"
    status_code = 422


# Exception Handlers


def handle_api_exception(request, exception: BaseAPIException) -> JsonResponse:
    """Handle custom API exceptions and return JSON response."""
    return JsonResponse(exception.to_dict(), status=exception.status_code)


def handle_validation_error(request, exception: ValidationError) -> JsonResponse:
    """Handle validation exceptions with field-specific errors."""
    response_data = exception.to_dict()

    # Add field errors if available
    if hasattr(exception, "field_errors"):
        response_data["field_errors"] = exception.field_errors

    return JsonResponse(response_data, status=exception.status_code)


def handle_ninja_http_error(request, exception: HttpError) -> JsonResponse:
    """Handle Django Ninja HTTP errors."""
    return JsonResponse(
        {"error": True, "message": str(exception), "code": "http_error"},
        status=exception.status_code,
    )


def handle_generic_exception(request, exception: Exception) -> JsonResponse:
    """Handle generic exceptions in production."""
    # In production, log the full exception but don't expose details
    logger.exception("Unhandled exception occurred")

    return JsonResponse(
        {
            "error": True,
            "message": "An internal error occurred",
            "code": "internal_error",
        },
        status=500,
    )


# Exception decorators


def handle_exceptions(func):
    """Decorator to handle exceptions in views."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseAPIException as e:
            request = args[0] if args else None
            return handle_api_exception(request, e)
        except Exception as e:
            request = args[0] if args else None
            return handle_generic_exception(request, e)

    return wrapper


def validate_required_fields(required_fields: list):
    """Decorator to validate required fields in request data."""

    def decorator(func):
        def wrapper(request, *args, **kwargs):
            if hasattr(request, "json") and request.json:
                data = request.json
            else:
                data = request.POST

            missing_fields = [
                field
                for field in required_fields
                if field not in data or not data[field]
            ]

            if missing_fields:
                raise ValidationError(
                    message=f"Missing required fields: {', '.join(missing_fields)}",
                    details={"missing_fields": missing_fields},
                )

            return func(request, *args, **kwargs)

        return wrapper

    return decorator
