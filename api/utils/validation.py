"""Validation utilities."""

import re
from dataclasses import dataclass, field
from typing import Any

# Constants for validation
MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 15
MIN_PASSWORD_LENGTH = 8


@dataclass
class ValidationResult:
    """Result of validation operations."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    field_errors: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str, field: str | None = None) -> None:
        """Add an error to the result."""
        self.is_valid = False
        if field:
            if field not in self.field_errors:
                self.field_errors[field] = []
            self.field_errors[field].append(message)
        else:
            self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(message)


def create_error_response(validation_result: ValidationResult) -> dict[str, Any]:
    """Create an error response from validation result.

    Args:
        validation_result: The validation result

    Returns:
        Dictionary suitable for API error response
    """
    return {
        "error": "Validation failed",
        "errors": validation_result.errors,
        "field_errors": validation_result.field_errors,
        "warnings": validation_result.warnings,
    }


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
    is_valid = True
    errors: list[str] = []
    score = 0

    # Check minimum length
    if len(password) < MIN_PASSWORD_LENGTH:
        is_valid = False
        errors.append("Password must be at least 8 characters long")
    else:
        score += 1

    # Check for uppercase letter
    if not re.search(r"[A-Z]", password):
        is_valid = False
        errors.append("Password must contain at least one uppercase letter")
    else:
        score += 1

    # Check for lowercase letter
    if not re.search(r"[a-z]", password):
        is_valid = False
        errors.append("Password must contain at least one lowercase letter")
    else:
        score += 1

    # Check for digit
    if not re.search(r"\d", password):
        is_valid = False
        errors.append("Password must contain at least one digit")
    else:
        score += 1

    # Check for special character
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        is_valid = False
        errors.append("Password must contain at least one special character")
    else:
        score += 1

    return {"is_valid": is_valid, "errors": errors, "score": score}


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
