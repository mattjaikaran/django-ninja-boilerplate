"""Decorator system for the django-ninja-boilerplate API.

This module provides decorators for error handling, logging, validation,
authentication, and rate limiting.
"""

import functools
import hashlib
import logging
import time
from collections.abc import Callable

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404

from .utils.validation import ValidationResult, create_error_response

logger = logging.getLogger(__name__)

# Fields whose values are always scrubbed before logging
SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "password1",
        "password2",
        "new_password",
        "old_password",
        "current_password",
        "confirm_password",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "secret_key",
        "api_key",
        "private_key",
        "authorization",
        "credit_card",
        "card_number",
        "cvv",
        "ssn",
    }
)


def _scrub(data: dict) -> dict:
    return {k: "***" if k.lower() in SENSITIVE_FIELDS else v for k, v in data.items()}


# Constants
TUPLE_RESPONSE_LENGTH = 2
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429
HTTP_INTERNAL_SERVER_ERROR = 500


def handle_exceptions(
    return_500_on_error: bool = True,
    log_errors: bool = True,
    custom_error_handler: Callable | None = None,
):
    """Decorator to handle exceptions in controller methods.

    Args:
        return_500_on_error: Whether to return 500 status on unhandled errors
        log_errors: Whether to log errors
        custom_error_handler: Custom function to handle specific errors
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)

            except Http404 as e:
                return HTTP_NOT_FOUND, {
                    "error": "Not found",
                    "message": str(e) or "The requested resource was not found",
                }

            except PermissionDenied as e:
                return HTTP_FORBIDDEN, {
                    "error": "Permission denied",
                    "message": str(e)
                    or "You do not have permission to perform this action",
                }

            except Exception as e:
                if log_errors:
                    logger.exception(
                        "Unhandled exception in %s",
                        func.__name__,
                        extra={
                            "method": func.__name__,
                            "call_args": args,
                            "call_kwargs": {
                                k: v for k, v in kwargs.items() if k != "payload"
                            },  # Exclude sensitive data
                        },
                    )

                # Try custom error handler first
                if custom_error_handler:
                    try:
                        return custom_error_handler(e, func.__name__)
                    except Exception:
                        logger.exception("Custom error handler failed")

                # Default error handling
                if return_500_on_error:
                    return HTTP_INTERNAL_SERVER_ERROR, {
                        "error": "Internal server error",
                        "message": "An unexpected error occurred",
                        "details": (
                            str(e) if logger.isEnabledFor(logging.DEBUG) else None
                        ),
                    }
                # Re-raise the exception
                raise

        return wrapper

    return decorator


def log_api_call(
    include_payload: bool = False,
    include_response: bool = False,
    log_level: int = logging.INFO,
):
    """Decorator to log API calls with timing and optional payload/response data.

    Args:
        include_payload: Whether to log request payload
        include_response: Whether to log response data
        log_level: Logging level to use
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()

            # Log the incoming request
            log_data = {
                "method": func.__name__,
                "call_args": args or None,
            }

            if include_payload and "payload" in kwargs:
                payload = kwargs["payload"]
                if hasattr(payload, "model_dump"):
                    log_data["payload"] = _scrub(payload.model_dump())
                else:
                    log_data["payload"] = str(payload)

            logger.log(log_level, "API call started: %s", func.__name__, extra=log_data)

            try:
                # Execute the function
                result = func(self, *args, **kwargs)

                # Calculate execution time
                execution_time = time.time() - start_time

                # Log the response
                log_data = {
                    "method": func.__name__,
                    "execution_time": f"{execution_time:.3f}s",
                    "success": True,
                }

                if include_response and result:
                    # Handle tuple responses (status_code, data)
                    if (
                        isinstance(result, tuple)
                        and len(result) == TUPLE_RESPONSE_LENGTH
                    ):
                        status_code, response_data = result
                        log_data["status_code"] = status_code
                        if status_code < HTTP_BAD_REQUEST:
                            log_data["response_size"] = (
                                len(str(response_data)) if response_data else 0
                            )
                    else:
                        log_data["response_size"] = len(str(result))

                logger.log(
                    log_level, "API call completed: %s", func.__name__, extra=log_data
                )

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                # Log the error
                log_data = {
                    "method": func.__name__,
                    "execution_time": f"{execution_time:.3f}s",
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }

                logger.exception("API call failed: %s", func.__name__, extra=log_data)

                # Re-raise the exception
                raise

        return wrapper

    return decorator


def validate_request(validators: list[Callable] | None = None):
    """Decorator to validate request data before processing.

    Args:
        validators: List of validation functions to run
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Extract payload from kwargs if it exists
            payload = kwargs.get("payload")

            if payload and validators:
                validation_result = ValidationResult()

                # Run custom validators
                for validator in validators:
                    result = validator(
                        payload.model_dump()
                        if hasattr(payload, "model_dump")
                        else payload
                    )
                    if not result.is_valid:
                        validation_result.is_valid = False
                        validation_result.errors.extend(result.errors)
                        validation_result.field_errors.update(result.field_errors)
                    validation_result.warnings.extend(result.warnings)

                # If validation fails, return error response
                if not validation_result.is_valid:
                    error_response = create_error_response(validation_result)
                    return HTTP_BAD_REQUEST, error_response

                # Log warnings
                for warning in validation_result.warnings:
                    logger.warning(
                        "Validation warning in %s: %s", func.__name__, warning
                    )

            # Proceed with the original function
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def require_authentication(allow_anonymous: bool = False):
    """Decorator to require authentication on controller methods.

    Args:
        allow_anonymous: If True, allow anonymous access but still set user context
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Find the request object in args
            request = None
            for arg in args:
                if hasattr(arg, "user"):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            if request is None:
                return HTTP_UNAUTHORIZED, {
                    "error": "Authentication required",
                    "message": "No request context available",
                }

            is_authenticated = (hasattr(request, "auth") and request.auth) or (
                hasattr(request, "user")
                and request.user
                and request.user.is_authenticated
            )

            if not is_authenticated and not allow_anonymous:
                return HTTP_UNAUTHORIZED, {
                    "error": "Authentication required",
                    "message": "You must be logged in to access this resource",
                }

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def require_verified(func):
    """Decorator to require email verification on controller methods."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        request = None
        for arg in args:
            if hasattr(arg, "user"):
                request = arg
                break
        if request is None:
            request = kwargs.get("request")

        if request is None or not hasattr(request, "user") or not request.user:
            return HTTP_UNAUTHORIZED, {
                "error": "Authentication required",
                "message": "You must be logged in to access this resource",
            }

        if not request.user.is_authenticated:
            return HTTP_UNAUTHORIZED, {
                "error": "Authentication required",
                "message": "You must be logged in to access this resource",
            }

        if not getattr(request.user, "is_verified", False):
            return HTTP_FORBIDDEN, {
                "error": "Email not verified",
                "message": "You must verify your email to access this resource",
            }

        return func(self, *args, **kwargs)

    return wrapper


def rate_limit(
    requests_per_minute: int = 60,
    key_func: Callable | None = None,
):
    """Decorator for per-endpoint rate limiting using the cache backend.

    Uses a sliding window counter stored in Django's cache framework.
    Adds X-RateLimit-* headers to the request META for the middleware to pick up.

    Args:
        requests_per_minute: Maximum requests allowed per minute
        key_func: Custom function to generate the rate limit key.
                  Receives (request, func_name) and returns a string.
    """
    period = 60  # 1 minute window

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Find the request object
            request = None
            for arg in args:
                if hasattr(arg, "META"):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            if request is None:
                # No request object found, skip rate limiting
                return func(self, *args, **kwargs)

            # Generate rate limit key
            if key_func:
                identifier = key_func(request, func.__name__)
            elif (
                hasattr(request, "user")
                and request.user
                and request.user.is_authenticated
            ):
                identifier = f"user:{request.user.pk}"
            else:
                ip = _get_client_ip(request)
                identifier = f"ip:{ip}"

            cache_key = f"ratelimit:{func.__name__}:{hashlib.md5(identifier.encode()).hexdigest()}"

            # Sliding window counter
            current_count = cache.get(cache_key, 0)

            # Set rate limit headers on request META for middleware
            request.META["X-RateLimit-Limit"] = str(requests_per_minute)
            request.META["X-RateLimit-Remaining"] = str(
                max(0, requests_per_minute - current_count - 1)
            )

            if current_count >= requests_per_minute:
                logger.warning(
                    "Rate limit exceeded for %s on %s",
                    identifier,
                    func.__name__,
                )
                return HTTP_TOO_MANY_REQUESTS, {
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {requests_per_minute}/min",
                }

            # Increment counter
            try:
                cache.set(cache_key, current_count + 1, timeout=period)
            except Exception:
                # If cache is unavailable, allow the request
                logger.warning("Rate limit cache unavailable, allowing request")

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def _get_client_ip(request) -> str:
    """Extract client IP from request, handling proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
