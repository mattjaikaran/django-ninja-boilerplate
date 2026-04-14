"""API utilities module.

This module provides common utility functions and helpers used across the django-ninja-boilerplate API.
"""

from .formatting import create_slug, format_phone_number, sanitize_string, truncate_text
from .http import (
    build_absolute_uri,
    get_client_ip,
    get_request_protocol,
    get_user_agent,
    is_ajax,
    is_mobile_request,
)
from .http_client import HttpClient, HttpClientError, http_client
from .validation import (
    convert_to_bool,
    validate_email,
    validate_password_strength,
    validate_phone_number,
    validate_username,
)

__all__ = [
    # Formatting utilities
    "create_slug",
    "format_phone_number",
    "sanitize_string",
    "truncate_text",
    # HTTP client
    "HttpClient",
    "HttpClientError",
    "http_client",
    # HTTP utilities
    "build_absolute_uri",
    "get_client_ip",
    "get_request_protocol",
    "get_user_agent",
    "is_ajax",
    "is_mobile_request",
    # Validation utilities
    "convert_to_bool",
    "validate_email",
    "validate_password_strength",
    "validate_phone_number",
    "validate_username",
]
