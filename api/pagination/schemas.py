"""Pagination schema definitions."""

from typing import Any, Generic, TypeVar

from ninja import Schema
from pydantic import Field

T = TypeVar("T")


class PaginationMeta(Schema):
    """Pagination metadata schema."""

    current_page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")
    next_page: int | None = Field(None, description="Next page number")
    previous_page: int | None = Field(None, description="Previous page number")
    start_index: int = Field(..., description="Index of first item on current page")
    end_index: int = Field(..., description="Index of last item on current page")


class PaginatedResponse(Schema, Generic[T]):
    """Generic paginated response schema."""

    items: list[T] = Field(..., description="List of items for current page")
    meta: PaginationMeta = Field(..., description="Pagination metadata")
    filters_applied: dict[str, Any] | None = Field(None, description="Applied filters")


class PaginationParams(Schema):
    """Pagination parameters schema."""

    page: int = Field(1, description="Page number", ge=1)
    per_page: int = Field(20, description="Items per page", ge=1, le=100)


class CursorPaginationParams(Schema):
    """Cursor-based pagination parameters."""

    limit: int = Field(20, description="Maximum items to return", ge=1, le=100)
    cursor: str | None = Field(None, description="Cursor for pagination")


class CursorPaginationMeta(Schema):
    """Cursor pagination metadata."""

    has_next: bool = Field(..., description="Whether there are more items")
    has_previous: bool = Field(..., description="Whether there are previous items")
    next_cursor: str | None = Field(None, description="Cursor for next page")
    previous_cursor: str | None = Field(None, description="Cursor for previous page")
    count: int = Field(..., description="Number of items in current page")


class CursorPaginatedResponse(Schema, Generic[T]):
    """Cursor-based paginated response schema."""

    items: list[T] = Field(..., description="List of items")
    meta: CursorPaginationMeta = Field(..., description="Cursor pagination metadata")
