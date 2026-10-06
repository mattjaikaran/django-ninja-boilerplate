"""Authentication schemas for API request/response validation.

This module defines Pydantic schemas for authentication-related API operations.
"""

from pydantic import EmailStr, Field

from core.schemas.base_schema import CamelCaseSchema
from core.schemas.user_schema import UserSchema

# Django's AbstractBaseUser.password and username columns.
_PASSWORD_MAX_LENGTH = 128
_USERNAME_MAX_LENGTH = 150


class PasswordlessLoginRequest(CamelCaseSchema):
    """Schema for requesting passwordless login magic link."""

    email: EmailStr


class PasswordlessLoginVerify(CamelCaseSchema):
    """Schema for verifying passwordless login token."""

    token: str = Field(min_length=1, max_length=255)


class LoginSchema(CamelCaseSchema):
    """Schema for email/password login.

    Note: The User model uses email as the primary authentication field.
    """

    email: EmailStr
    password: str = Field(min_length=1, max_length=_PASSWORD_MAX_LENGTH)


class TokenSchema(CamelCaseSchema):
    """Login response.

    Browser clients ignore the token fields: login also sets httpOnly auth
    cookies (docs/COOKIE_AUTH.md). Bearer clients read them.
    """

    token: str
    refresh: str
    user: UserSchema


class PasswordlessTokenSchema(CamelCaseSchema):
    """Magic-link verification response. Also sets httpOnly auth cookies."""

    access: str
    refresh: str
    user: UserSchema


class RefreshTokenSchema(CamelCaseSchema):
    """Refresh token in the body. Browser clients omit it and use the cookie."""

    refresh: str | None = Field(default=None, min_length=1)


class TokenRefreshResponse(CamelCaseSchema):
    """Rotated token pair.

    Both fields are null when the refresh token came from the cookie: cookie
    clients get new cookies, never tokens in the body.
    """

    access: str | None = None
    refresh: str | None = None


class CsrfTokenSchema(CamelCaseSchema):
    """CSRF token, also set as the readable ``csrftoken`` cookie."""

    csrf_token: str


class PasswordResetRequestSchema(CamelCaseSchema):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirmSchema(CamelCaseSchema):
    """Schema for password reset confirmation."""

    token: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=_PASSWORD_MAX_LENGTH)


class EmailVerificationSchema(CamelCaseSchema):
    """Schema for email verification."""

    token: str = Field(min_length=1, max_length=255)


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

    username: str = Field(min_length=1, max_length=_USERNAME_MAX_LENGTH)
    password: str = Field(min_length=1, max_length=_PASSWORD_MAX_LENGTH)
