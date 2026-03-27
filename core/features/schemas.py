"""Feature Flag Schemas.

Pydantic schemas for feature flag API requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from core.schemas.base_schema import CamelCaseSchema


class FlagTypeEnum(str, Enum):
    """Feature flag types."""

    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    AB_TEST = "ab_test"


# =============================================================================
# Request Schemas
# =============================================================================


class FeatureFlagCreateSchema(CamelCaseSchema):
    """Schema for creating a feature flag."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Unique name for the flag (snake_case)",
    )
    description: str = Field(
        default="",
        max_length=500,
        description="Description of what this flag controls",
    )
    flag_type: FlagTypeEnum = Field(
        default=FlagTypeEnum.BOOLEAN,
        description="Type of feature flag",
    )
    enabled: bool = Field(
        default=False,
        description="Whether the flag is enabled",
    )
    rollout_percentage: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Percentage rollout (0-100)",
    )
    user_ids: list[str] = Field(
        default_factory=list,
        description="List of user IDs that have this flag enabled",
    )
    excluded_user_ids: list[str] = Field(
        default_factory=list,
        description="List of user IDs excluded from this flag",
    )
    variants: dict[str, int] = Field(
        default_factory=dict,
        description="A/B test variants with weights (must sum to 100)",
    )
    default_variant: str = Field(
        default="control",
        description="Default variant for A/B tests",
    )
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Advanced conditions for flag evaluation",
    )
    environments: list[str] = Field(
        default_factory=list,
        description="Environments where this flag is active (empty = all)",
    )
    starts_at: datetime | None = Field(
        default=None,
        description="When this flag should start being active",
    )
    ends_at: datetime | None = Field(
        default=None,
        description="When this flag should stop being active",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for organizing flags",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    @field_validator("variants")
    @classmethod
    def validate_variants(cls, v: dict[str, int]) -> dict[str, int]:
        """Validate that variant weights sum to 100 if provided."""
        if v and sum(v.values()) != 100:
            raise ValueError("Variant weights must sum to 100")
        return v


class FeatureFlagUpdateSchema(CamelCaseSchema):
    """Schema for updating a feature flag."""

    description: str | None = None
    flag_type: FlagTypeEnum | None = None
    enabled: bool | None = None
    rollout_percentage: int | None = Field(default=None, ge=0, le=100)
    user_ids: list[str] | None = None
    excluded_user_ids: list[str] | None = None
    variants: dict[str, int] | None = None
    default_variant: str | None = None
    conditions: dict[str, Any] | None = None
    environments: list[str] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("variants")
    @classmethod
    def validate_variants(cls, v: dict[str, int] | None) -> dict[str, int] | None:
        """Validate that variant weights sum to 100 if provided."""
        if v and sum(v.values()) != 100:
            raise ValueError("Variant weights must sum to 100")
        return v


class FeatureFlagToggleSchema(CamelCaseSchema):
    """Schema for toggling a feature flag."""

    enabled: bool = Field(..., description="New enabled state")


class RolloutUpdateSchema(CamelCaseSchema):
    """Schema for updating rollout percentage."""

    percentage: int = Field(
        ...,
        ge=0,
        le=100,
        description="New rollout percentage (0-100)",
    )


class UserFlagSchema(CamelCaseSchema):
    """Schema for adding/removing users from flags."""

    user_id: str = Field(..., description="User ID to add/remove")


class CheckFlagSchema(CamelCaseSchema):
    """Schema for checking flag status."""

    flag_name: str = Field(..., description="Name of the flag to check")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for evaluation",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class FeatureFlagSchema(CamelCaseSchema):
    """Schema for feature flag response."""

    id: UUID
    name: str
    description: str
    flag_type: str
    enabled: bool
    rollout_percentage: int
    user_ids: list[str]
    excluded_user_ids: list[str]
    variants: dict[str, int]
    default_variant: str
    conditions: dict[str, Any]
    environments: list[str]
    starts_at: datetime | None
    ends_at: datetime | None
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class FeatureFlagListSchema(CamelCaseSchema):
    """Schema for listing feature flags."""

    id: UUID
    name: str
    description: str
    flag_type: str
    enabled: bool
    rollout_percentage: int
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class FlagStatusSchema(CamelCaseSchema):
    """Schema for flag status check response."""

    flag_name: str
    enabled: bool
    variant: str | None = None


class UserFlagsSchema(CamelCaseSchema):
    """Schema for user's feature flags response."""

    flags: dict[str, bool | str]


class FlagAuditLogSchema(CamelCaseSchema):
    """Schema for feature flag audit log."""

    id: UUID
    action: str
    changes: dict[str, Any]
    user_id: UUID | None = None
    created_at: datetime


class FeatureFlagWithAuditSchema(FeatureFlagSchema):
    """Schema for feature flag with audit logs."""

    audit_logs: list[FlagAuditLogSchema] = []


# =============================================================================
# Bulk Operation Schemas
# =============================================================================


class BulkFlagToggleSchema(CamelCaseSchema):
    """Schema for bulk toggling flags."""

    flag_names: list[str] = Field(..., description="List of flag names to toggle")
    enabled: bool = Field(..., description="New enabled state for all flags")


class BulkFlagResponseSchema(CamelCaseSchema):
    """Response schema for bulk operations."""

    success: bool = True
    updated: int = 0
    failed: list[str] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)
