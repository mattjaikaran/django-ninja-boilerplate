"""Base schema classes for consistent API responses.

This module provides base Pydantic schemas for standardized API responses
including error handling, pagination, and common response patterns.

All API schemas should inherit from ``CamelCaseSchema`` for consistent
camelCase JSON field names.  Input schemas accept **both** camelCase and
snake_case thanks to ``populate_by_name=True``; output always serialises
as camelCase.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel

# Type variable for generic responses
T = TypeVar("T")


# =============================================================================
# CamelCase Base Schema
# =============================================================================


class CamelCaseSchema(Schema):
    """Base schema with automatic camelCase aliases.

    Features:
        - ``alias_generator=to_camel``: field ``first_name`` → JSON key ``firstName``
        - ``populate_by_name=True``: input accepts both ``firstName`` and ``first_name``
        - ``model_dump`` overridden to always serialise by alias (camelCase),
          which is required because Django Ninja passes ``by_alias=False`` by default.

    Usage::

        class UserSchema(CamelCaseSchema):
            first_name: str
            last_name: str


        # Serialises as {"firstName": "...", "lastName": "..."}
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Always serialise using camelCase aliases.

        Django Ninja calls ``model_dump(by_alias=False)`` by default.
        This override forces ``by_alias=True`` so JSON responses use
        the camelCase aliases produced by the alias generator.
        """
        kwargs["by_alias"] = True
        return super().model_dump(**kwargs)


# =============================================================================
# Common Response Schemas
# =============================================================================


class SuccessResponse(CamelCaseSchema):
    """Standard success response schema."""

    success: bool = True
    message: str = "Operation completed successfully"


class ErrorResponse(CamelCaseSchema):
    """Standard error response schema."""

    model_config = ConfigDict(extra="ignore")

    error: bool = True
    message: str
    code: str = "error"
    details: dict[str, Any] | None = None


class ValidationErrorResponse(CamelCaseSchema):
    """Validation error response with field-specific errors."""

    error: bool = True
    message: str = "Validation failed"
    code: str = "validation_error"
    field_errors: dict[str, list[str]] = Field(default_factory=dict)


class MessageResponse(CamelCaseSchema):
    """Simple message response."""

    message: str
    success: bool = True


class IdResponse(CamelCaseSchema):
    """Response containing just an ID."""

    id: str | UUID


# =============================================================================
# Pagination Schemas
# =============================================================================


class PaginationMeta(CamelCaseSchema):
    """Pagination metadata for list responses."""

    page: int = 1
    per_page: int = 50
    total: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_prev: bool = False


class PaginatedResponse(CamelCaseSchema, Generic[T]):
    """Paginated list response wrapper."""

    items: list[T]
    meta: PaginationMeta


# =============================================================================
# Timestamp and Audit Schemas
# =============================================================================


class TimestampSchema(CamelCaseSchema):
    """Schema with timestamp fields."""

    created_at: datetime
    updated_at: datetime


class AuditSchema(TimestampSchema):
    """Schema with full audit fields."""

    created_by_id: str | UUID | None = None
    updated_by_id: str | UUID | None = None


class BaseModelSchema(CamelCaseSchema):
    """Base schema for all model responses."""

    id: str | UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_active: bool = True


# =============================================================================
# Filter and Sort Schemas
# =============================================================================


class SortOrder(str, Enum):
    """Sort order enumeration."""

    ASC = "asc"
    DESC = "desc"


class BaseSortSchema(CamelCaseSchema):
    """Base schema for sorting parameters."""

    sort_by: str | None = None
    sort_order: SortOrder = SortOrder.DESC


class BaseFilterSchema(CamelCaseSchema):
    """Base schema for filtering parameters."""

    search: str | None = None
    is_active: bool | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


class DateRangeSchema(CamelCaseSchema):
    """Date range filter schema."""

    start_date: datetime | None = None
    end_date: datetime | None = None


# =============================================================================
# Status Schemas
# =============================================================================


class StatusEnum(str, Enum):
    """Common status enumeration."""

    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class StatusUpdateSchema(CamelCaseSchema):
    """Schema for status updates."""

    status: StatusEnum


class BulkActionSchema(CamelCaseSchema):
    """Schema for bulk actions on multiple items."""

    ids: list[str | UUID]
    action: str


class BulkActionResponse(CamelCaseSchema):
    """Response for bulk actions."""

    success: bool = True
    processed: int = 0
    failed: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Health Check Schemas
# =============================================================================


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceHealth(CamelCaseSchema):
    """Individual service health status."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None


class HealthCheckResponse(CamelCaseSchema):
    """Complete health check response."""

    status: HealthStatus
    version: str | None = None
    environment: str | None = None
    services: list[ServiceHealth] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Utility Functions
# =============================================================================


def create_paginated_response(
    items: list,
    page: int = 1,
    per_page: int = 50,
    total: int = 0,
) -> dict:
    """Create a paginated response dictionary.

    Args:
        items: List of items for current page
        page: Current page number
        per_page: Items per page
        total: Total count of items

    Returns:
        Dictionary with items and pagination metadata
    """
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    return {
        "items": items,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


def create_error_response(
    message: str,
    code: str = "error",
    details: dict | None = None,
) -> dict:
    """Create a standard error response dictionary.

    Args:
        message: Error message
        code: Error code
        details: Additional error details

    Returns:
        Error response dictionary
    """
    response = {
        "error": True,
        "message": message,
        "code": code,
    }
    if details:
        response["details"] = details
    return response


def create_success_response(
    message: str = "Operation completed successfully",
    data: dict | None = None,
) -> dict:
    """Create a standard success response dictionary.

    Args:
        message: Success message
        data: Additional response data

    Returns:
        Success response dictionary
    """
    response = {
        "success": True,
        "message": message,
    }
    if data:
        response.update(data)
    return response
