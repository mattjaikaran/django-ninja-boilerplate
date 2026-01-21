"""Base schema classes for consistent API responses.

This module provides base Pydantic schemas for standardized API responses
including error handling, pagination, and common response patterns.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID

from ninja import Schema
from pydantic import Field

# Type variable for generic responses
T = TypeVar("T")


# =============================================================================
# Common Response Schemas
# =============================================================================


class SuccessResponse(Schema):
    """Standard success response schema."""

    success: bool = True
    message: str = "Operation completed successfully"


class ErrorResponse(Schema):
    """Standard error response schema."""

    error: bool = True
    message: str
    code: str = "error"
    details: dict[str, Any] | None = None


class ValidationErrorResponse(Schema):
    """Validation error response with field-specific errors."""

    error: bool = True
    message: str = "Validation failed"
    code: str = "validation_error"
    field_errors: dict[str, list[str]] = Field(default_factory=dict)


class MessageResponse(Schema):
    """Simple message response."""

    message: str
    success: bool = True


class IdResponse(Schema):
    """Response containing just an ID."""

    id: str | UUID


# =============================================================================
# Pagination Schemas
# =============================================================================


class PaginationMeta(Schema):
    """Pagination metadata for list responses."""

    page: int = 1
    per_page: int = 50
    total: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_prev: bool = False


class PaginatedResponse(Schema, Generic[T]):
    """Paginated list response wrapper."""

    items: list[T]
    meta: PaginationMeta


# =============================================================================
# Timestamp and Audit Schemas
# =============================================================================


class TimestampSchema(Schema):
    """Schema with timestamp fields."""

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AuditSchema(TimestampSchema):
    """Schema with full audit fields."""

    created_by_id: str | UUID | None = None
    updated_by_id: str | UUID | None = None

    class Config:
        from_attributes = True


class BaseModelSchema(Schema):
    """Base schema for all model responses."""

    id: str | UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_active: bool = True

    class Config:
        from_attributes = True


# =============================================================================
# Filter and Sort Schemas
# =============================================================================


class SortOrder(str, Enum):
    """Sort order enumeration."""

    ASC = "asc"
    DESC = "desc"


class BaseSortSchema(Schema):
    """Base schema for sorting parameters."""

    sort_by: str | None = None
    sort_order: SortOrder = SortOrder.DESC


class BaseFilterSchema(Schema):
    """Base schema for filtering parameters."""

    search: str | None = None
    is_active: bool | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


class DateRangeSchema(Schema):
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


class StatusUpdateSchema(Schema):
    """Schema for status updates."""

    status: StatusEnum


class BulkActionSchema(Schema):
    """Schema for bulk actions on multiple items."""

    ids: list[str | UUID]
    action: str


class BulkActionResponse(Schema):
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


class ServiceHealth(Schema):
    """Individual service health status."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None


class HealthCheckResponse(Schema):
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
