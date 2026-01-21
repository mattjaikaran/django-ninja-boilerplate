"""Authentication schemas for API request/response validation.

This module defines Pydantic schemas for authentication-related API operations.
"""

from ninja import Schema
from pydantic import EmailStr, Field, field_validator


class PasswordlessLoginRequest(Schema):
    """Schema for requesting passwordless login magic link."""

    email: EmailStr


class PasswordlessLoginVerify(Schema):
    """Schema for verifying passwordless login token."""

    token: str


class LoginSchema(Schema):
    """Schema for email/password login.

    Note: The User model uses email as the primary authentication field.
    """

    email: EmailStr
    password: str


class TokenSchema(Schema):
    """Schema for authentication token response."""

    token: str
    refresh: str
    user: dict


class RefreshTokenSchema(Schema):
    """Schema for token refresh request."""

    refresh: str


class PasswordResetRequestSchema(Schema):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirmSchema(Schema):
    """Schema for password reset confirmation."""

    token: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_requirements(cls, v: str) -> str:
        """Validate password meets requirements."""
        if len(v) < 8:
            msg = "Password must be at least 8 characters"
            raise ValueError(msg)
        return v


class EmailVerificationSchema(Schema):
    """Schema for email verification."""

    token: str


class AuthStatusSchema(Schema):
    """Schema for authentication status response."""

    authenticated: bool
    user_id: str | None = None
    email: str | None = None


# Legacy schemas for backwards compatibility
class UserLoginSchema(Schema):
    """Legacy login schema using username.

    Deprecated: Use LoginSchema instead.
    """

    username: str
    password: str
