"""Simple decorator system for the django-ninja-boilerplate API.

This module provides decorators for error handling, logging, and validation.
"""

import functools
import logging
import time
from collections.abc import Callable

from django.http import Http404

from .utils.validation import ValidationResult, create_error_response

logger = logging.getLogger(__name__)

# Constants
TUPLE_RESPONSE_LENGTH = 2
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
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
                # Handle 404 errors specially - return proper 404 response
                return HTTP_NOT_FOUND, {
                    "error": "Not found",
                    "message": str(e) if str(e) else "The requested resource was not found",
                }

            except Exception as e:
                if log_errors:
                    logger.exception(
                        "Unhandled exception in %s: %s",
                        func.__name__,
                        str(e),
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
                    except Exception as handler_error:
                        logger.exception(
                            "Custom error handler failed: %s", str(handler_error)
                        )

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
                "call_args": args if args else None,
            }

            if include_payload and "payload" in kwargs:
                payload = kwargs["payload"]
                if hasattr(payload, "model_dump"):
                    log_data["payload"] = payload.model_dump()
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
