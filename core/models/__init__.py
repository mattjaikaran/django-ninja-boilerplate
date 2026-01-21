"""Core models package.

This module exports all model classes for the core app.
"""

from core.models.base import (
    AbstractBaseModel,
    ActiveManager,
    DeletedManager,
    SoftDeleteModel,
    TimestampedModel,
)
from core.models.otp import (
    OneTimePassword,
    OTPDeliveryMethod,
    OTPPurpose,
    OTPRateLimit,
)
from core.models.user import CustomUserManager, User

__all__ = [
    "AbstractBaseModel",
    "ActiveManager",
    "CustomUserManager",
    "DeletedManager",
    "OTPDeliveryMethod",
    "OTPPurpose",
    "OTPRateLimit",
    "OneTimePassword",
    "SoftDeleteModel",
    "TimestampedModel",
    "User",
]
