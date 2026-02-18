"""Core models package.

This module exports all model classes for the core app.
"""

from core.audit.models import AuditAction, AuditLog
from core.features.models import FeatureFlag, FeatureFlagAuditLog, FlagType
from core.models.base import (
    AbstractBaseModel,
    ActiveManager,
    AuditBaseModel,
    DeletedManager,
    SoftDeleteBaseModel,
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
from core.tasks.models import DeadLetterQueueEntry, TaskResult, TaskStatus

__all__ = [
    "AbstractBaseModel",
    "ActiveManager",
    "AuditAction",
    "AuditBaseModel",
    "AuditLog",
    "CustomUserManager",
    "DeadLetterQueueEntry",
    "DeletedManager",
    "FeatureFlag",
    "FeatureFlagAuditLog",
    "FlagType",
    "OTPDeliveryMethod",
    "OTPPurpose",
    "OTPRateLimit",
    "OneTimePassword",
    "SoftDeleteBaseModel",
    "SoftDeleteModel",
    "TaskResult",
    "TaskStatus",
    "TimestampedModel",
    "User",
]
