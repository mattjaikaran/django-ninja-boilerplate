"""User schemas for API request/response validation.

This module defines Pydantic schemas for user-related API operations.
"""

from datetime import datetime

from ninja import Schema
from pydantic import EmailStr, Field, field_validator


class UserSchema(Schema):
    """Schema for user responses."""

    id: str
    email: EmailStr
    username: str
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    avatar: str | None = None
    bio: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    timezone: str = "UTC"
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False
    is_verified: bool = False
    email_notifications: bool = True
    push_notifications: bool = True
    date_joined: datetime | None = None
    last_login: datetime | None = None

    class Config:
        from_attributes = True


class UserBasicSchema(Schema):
    """Minimal user schema for embedded responses."""

    id: str
    email: EmailStr
    username: str
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    avatar: str | None = None

    class Config:
        from_attributes = True


class UserSignupSchema(Schema):
    """Schema for user registration."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    first_name: str = Field("", max_length=100)
    last_name: str = Field("", max_length=100)
    is_staff: bool = False
    is_superuser: bool = False

    @field_validator("password")
    @classmethod
    def password_requirements(cls, v: str) -> str:
        """Validate password meets requirements."""
        if len(v) < 8:
            msg = "Password must be at least 8 characters"
            raise ValueError(msg)
        return v


class UserLoginSchema(Schema):
    """Schema for user login."""

    email: EmailStr
    password: str


class UserLogoutSchema(Schema):
    """Schema for logout response."""

    message: str


class UserUpdateSchema(Schema):
    """Schema for updating user profile."""

    first_name: str | None = None
    last_name: str | None = None
    username: str | None = Field(None, min_length=3, max_length=100)
    bio: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=20)
    location: str | None = Field(None, max_length=200)
    website: str | None = None
    timezone: str | None = None
    email_notifications: bool | None = None
    push_notifications: bool | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for optional fields."""
        if v == "":
            return None
        return v

    class Config:
        from_attributes = True


class UserDeleteSchema(Schema):
    """Schema for user deletion response."""

    message: str


class ChangePasswordSchema(Schema):
    """Schema for password change."""

    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_requirements(cls, v: str) -> str:
        """Validate new password meets requirements."""
        if len(v) < 8:
            msg = "Password must be at least 8 characters"
            raise ValueError(msg)
        return v


class UserPreferencesSchema(Schema):
    """Schema for user preferences."""

    email_notifications: bool = True
    push_notifications: bool = True
    timezone: str = "UTC"

    class Config:
        from_attributes = True


class UserStatsSchema(Schema):
    """Schema for user statistics."""

    total_todos: int = 0
    completed_todos: int = 0
    pending_todos: int = 0
    completion_rate: float = 0.0
