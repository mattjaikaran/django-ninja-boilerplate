"""OTP schemas for API request/response validation.

This module defines Pydantic schemas for OTP-related API operations,
including mobile/iOS 6-digit code authentication.
"""

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from core.schemas.base_schema import CamelCaseSchema


class OTPRequestSchema(CamelCaseSchema):
    """Schema for requesting an OTP code.

    Used for mobile/iOS apps to request a 6-digit code.
    """

    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    purpose: str = Field(
        default="LOGIN",
        description="Purpose: LOGIN, SIGNUP_VERIFICATION, PASSWORD_RESET, EMAIL_CHANGE, PHONE_VERIFICATION, TWO_FACTOR",
    )
    delivery_method: str = Field(
        default="EMAIL",
        description="Delivery method: EMAIL, SMS, PUSH",
    )

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, v: str) -> str:
        """Validate purpose is valid."""
        valid_purposes = [
            "LOGIN",
            "SIGNUP_VERIFICATION",
            "PASSWORD_RESET",
            "EMAIL_CHANGE",
            "PHONE_VERIFICATION",
            "TWO_FACTOR",
        ]
        if v.upper() not in valid_purposes:
            msg = f"Invalid purpose. Must be one of: {', '.join(valid_purposes)}"
            raise ValueError(msg)
        return v.upper()

    @field_validator("delivery_method")
    @classmethod
    def validate_delivery_method(cls, v: str) -> str:
        """Validate delivery method is valid."""
        valid_methods = ["EMAIL", "SMS", "PUSH"]
        if v.upper() not in valid_methods:
            msg = f"Invalid delivery method. Must be one of: {', '.join(valid_methods)}"
            raise ValueError(msg)
        return v.upper()


class OTPVerifySchema(CamelCaseSchema):
    """Schema for verifying an OTP code.

    Used for mobile/iOS apps to verify a 6-digit code.
    """

    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    code: str = Field(..., min_length=6, max_length=6)
    purpose: str = Field(default="LOGIN")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code is 6 digits."""
        if not v.isdigit():
            msg = "Code must be 6 digits"
            raise ValueError(msg)
        return v


class OTPTokenVerifySchema(CamelCaseSchema):
    """Schema for verifying an OTP token (magic link)."""

    token: str = Field(..., min_length=32)


class OTPResponseSchema(CamelCaseSchema):
    """Schema for OTP request response."""

    success: bool
    message: str
    expires_in_seconds: int | None = None
    remaining_attempts: int | None = None


class OTPVerifyResponseSchema(CamelCaseSchema):
    """Schema for OTP verification response with tokens."""

    success: bool
    message: str
    access: str | None = None
    refresh: str | None = None
    user: dict | None = None


class OTPStatusSchema(CamelCaseSchema):
    """Schema for checking OTP status."""

    is_valid: bool
    is_expired: bool
    remaining_attempts: int
    expires_at: datetime | None = None
    purpose: str


class PasswordResetWithOTPSchema(CamelCaseSchema):
    """Schema for password reset using OTP code."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code is 6 digits."""
        if not v.isdigit():
            msg = "Code must be 6 digits"
            raise ValueError(msg)
        return v

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password requirements."""
        if len(v) < 8:
            msg = "Password must be at least 8 characters"
            raise ValueError(msg)
        return v


class SignupWithOTPSchema(CamelCaseSchema):
    """Schema for signup verification with OTP."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code is 6 digits."""
        if not v.isdigit():
            msg = "Code must be 6 digits"
            raise ValueError(msg)
        return v


class TwoFactorSetupSchema(CamelCaseSchema):
    """Schema for setting up two-factor authentication."""

    enable: bool = True
    delivery_method: str = Field(
        default="EMAIL",
        description="Delivery method for 2FA codes: EMAIL, SMS",
    )


class TwoFactorVerifySchema(CamelCaseSchema):
    """Schema for verifying two-factor authentication."""

    code: str = Field(..., min_length=6, max_length=6)
    remember_device: bool = Field(
        default=False,
        description="Remember this device for 30 days",
    )

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code is 6 digits."""
        if not v.isdigit():
            msg = "Code must be 6 digits"
            raise ValueError(msg)
        return v


class ResendOTPSchema(CamelCaseSchema):
    """Schema for resending an OTP code."""

    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    purpose: str = Field(default="LOGIN")
