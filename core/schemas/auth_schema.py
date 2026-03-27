"""Authentication schemas for API request/response validation.

This module defines Pydantic schemas for authentication-related API operations.
"""

from pydantic import EmailStr, Field, field_validator

from core.schemas.base_schema import CamelCaseSchema


class PasswordlessLoginRequest(CamelCaseSchema):
    """Schema for requesting passwordless login magic link."""

    email: EmailStr


class PasswordlessLoginVerify(CamelCaseSchema):
    """Schema for verifying passwordless login token."""

    token: str


class LoginSchema(CamelCaseSchema):
    """Schema for email/password login.

    Note: The User model uses email as the primary authentication field.
    """

    email: EmailStr
    password: str


class TokenSchema(CamelCaseSchema):
    """Schema for authentication token response."""

    token: str
    refresh: str
    user: dict


class RefreshTokenSchema(CamelCaseSchema):
    """Schema for token refresh request."""

    refresh: str


class PasswordResetRequestSchema(CamelCaseSchema):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirmSchema(CamelCaseSchema):
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


class EmailVerificationSchema(CamelCaseSchema):
    """Schema for email verification."""

    token: str


class AuthStatusSchema(CamelCaseSchema):
    """Schema for authentication status response."""

    authenticated: bool
    user_id: str | None = None
    email: str | None = None


# Legacy schemas for backwards compatibility
class UserLoginSchema(CamelCaseSchema):
    """Legacy login schema using username.

    Deprecated: Use LoginSchema instead.
    """

    username: str
    password: str
