"""Validation utilities."""

import re
from typing import Any

# Constants for validation
MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 15
MIN_PASSWORD_LENGTH = 8


def validate_email(email: str) -> bool:
    """Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if email is valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone_number(phone: str) -> bool:
    """Validate phone number format.

    Args:
        phone: Phone number to validate

    Returns:
        True if phone number is valid, False otherwise
    """
    # Remove all non-digit characters for validation
    digits = re.sub(r"\D", "", phone)
    # Valid phone numbers should have 10-15 digits
    return MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS


def validate_password_strength(password: str) -> dict[str, Any]:
    """Validate password strength.

    Args:
        password: Password to validate

    Returns:
        Dictionary with validation results and requirements
    """
    result = {
        "is_valid": True,
        "errors": [],
        "score": 0,
    }

    # Check minimum length
    if len(password) < MIN_PASSWORD_LENGTH:
        result["is_valid"] = False
        result["errors"].append("Password must be at least 8 characters long")
    else:
        result["score"] += 1

    # Check for uppercase letter
    if not re.search(r"[A-Z]", password):
        result["is_valid"] = False
        result["errors"].append("Password must contain at least one uppercase letter")
    else:
        result["score"] += 1

    # Check for lowercase letter
    if not re.search(r"[a-z]", password):
        result["is_valid"] = False
        result["errors"].append("Password must contain at least one lowercase letter")
    else:
        result["score"] += 1

    # Check for digit
    if not re.search(r"\d", password):
        result["is_valid"] = False
        result["errors"].append("Password must contain at least one digit")
    else:
        result["score"] += 1

    # Check for special character
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        result["is_valid"] = False
        result["errors"].append("Password must contain at least one special character")
    else:
        result["score"] += 1

    return result


def convert_to_bool(value: Any) -> bool:
    """Convert various value types to boolean.

    Args:
        value: Value to convert to boolean

    Returns:
        Boolean representation of the value
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on", "y")
    if isinstance(value, int | float):
        return bool(value)
    return False


def validate_username(username: str) -> bool:
    """Validate username format.

    Args:
        username: Username to validate

    Returns:
        True if username is valid, False otherwise
    """
    # Username should be 3-30 characters, alphanumeric with underscores/hyphens
    pattern = r"^[a-zA-Z0-9_-]{3,30}$"
    return bool(re.match(pattern, username))
