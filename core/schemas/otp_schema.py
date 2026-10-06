"""OTP schemas for API request/response validation.

This module defines Pydantic schemas for OTP-related API operations,
including mobile/iOS 6-digit code authentication.
"""

from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from core.schemas.base_schema import CamelCaseSchema
from core.schemas.user_schema import UserSchema

# Values match core.models.otp.OTPPurpose. Clients cannot request MAGIC_LINK
# codes, so the request literal leaves it out.
RequestableOTPPurpose = Literal[
    "LOGIN",
    "SIGNUP_VERIFICATION",
    "PASSWORD_RESET",
    "EMAIL_CHANGE",
    "PHONE_VERIFICATION",
    "TWO_FACTOR",
]
OTPPurposeValue = Literal[
    "LOGIN",
    "SIGNUP_VERIFICATION",
    "PASSWORD_RESET",
    "EMAIL_CHANGE",
    "PHONE_VERIFICATION",
    "TWO_FACTOR",
    "MAGIC_LINK",
]
# Values match core.models.otp.OTPDeliveryMethod.
OTPDeliveryMethodValue = Literal["EMAIL", "SMS", "PUSH"]

OTP_CODE_PATTERN = r"^[0-9]{6}$"


class OTPRequestSchema(CamelCaseSchema):
    """Schema for requesting an OTP code.

    Used for mobile/iOS apps to request a 6-digit code.
    """

    email: EmailStr | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    purpose: RequestableOTPPurpose = Field(
        default="LOGIN",
        description="Purpose of the code. Case-insensitive on input.",
    )
    delivery_method: OTPDeliveryMethodValue = Field(
        default="EMAIL",
        description="Delivery method. Case-insensitive on input.",
    )

    @field_validator("purpose", "delivery_method", mode="before")
    @classmethod
    def normalize_case(cls, v: object) -> object:
        """Accept lowercase input by upper-casing it before validation."""
        if isinstance(v, str):
            return v.upper()
        return v


class OTPVerifySchema(CamelCaseSchema):
    """Schema for verifying an OTP code.

    Used for mobile/iOS apps to verify a 6-digit code.
    """

    email: EmailStr | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    code: str = Field(..., min_length=6, max_length=6, pattern=OTP_CODE_PATTERN)
    purpose: RequestableOTPPurpose = "LOGIN"


class OTPTokenVerifySchema(CamelCaseSchema):
    """Schema for verifying an OTP token (magic link)."""

    token: str = Field(..., min_length=32, max_length=255)


class OTPResponseSchema(CamelCaseSchema):
    """Schema for OTP request response."""

    success: bool
    message: str
    expires_in_seconds: int | None = None
    remaining_attempts: int | None = None


class OTPVerifyResponseSchema(CamelCaseSchema):
    """OTP verification result; authentication is carried only by cookies."""

    success: bool
    message: str
    access: str | None = None
    refresh: str | None = None
    user: UserSchema | None = None


class OTPStatusSchema(CamelCaseSchema):
    """Schema for checking OTP status."""

    is_valid: bool
    is_expired: bool
    remaining_attempts: int
    expires_at: datetime | None = None
    purpose: OTPPurposeValue


class PasswordResetWithOTPSchema(CamelCaseSchema):
    """Schema for password reset using OTP code."""

    email: EmailStr = Field(..., max_length=255)
    code: str = Field(..., min_length=6, max_length=6, pattern=OTP_CODE_PATTERN)
    new_password: str = Field(..., min_length=8)


class SignupWithOTPSchema(CamelCaseSchema):
    """Schema for signup verification with OTP."""

    email: EmailStr = Field(..., max_length=255)
    code: str = Field(..., min_length=6, max_length=6, pattern=OTP_CODE_PATTERN)


class TwoFactorSetupSchema(CamelCaseSchema):
    """Schema for setting up two-factor authentication."""

    enable: bool = True
    delivery_method: Literal["EMAIL", "SMS"] = Field(
        default="EMAIL",
        description="Delivery method for 2FA codes",
    )


class TwoFactorVerifySchema(CamelCaseSchema):
    """Schema for verifying two-factor authentication."""

    code: str = Field(..., min_length=6, max_length=6, pattern=OTP_CODE_PATTERN)
    remember_device: bool = Field(
        default=False,
        description="Remember this device for 30 days",
    )


class ResendOTPSchema(CamelCaseSchema):
    """Schema for resending an OTP code."""

    email: EmailStr | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    purpose: RequestableOTPPurpose = "LOGIN"
