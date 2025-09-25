"""Advanced pagination utilities for Django Ninja APIs."""

from typing import Any, Generic, TypeVar

from django.core.paginator import Paginator
from django.db.models import QuerySet
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


class AdvancedPaginator:
    """Advanced paginator with enhanced functionality."""

    def __init__(
        self,
        queryset: QuerySet,
        per_page: int = 20,
        max_per_page: int = 100,
        orphans: int = 0,
    ):
        """Initialize paginator.

        Args:
            queryset: Django QuerySet to paginate
            per_page: Items per page
            max_per_page: Maximum allowed items per page
            orphans: Minimum items on last page (merge with previous if less)
        """
        self.queryset = queryset
        self.per_page = min(per_page, max_per_page)
        self.max_per_page = max_per_page
        self.orphans = orphans
        self._paginator = None

    @property
    def paginator(self) -> Paginator:
        """Get Django paginator instance."""
        if self._paginator is None:
            self._paginator = Paginator(
                self.queryset, self.per_page, orphans=self.orphans
            )
        return self._paginator

    def get_page(self, page_number: int = 1) -> dict[str, Any]:
        """Get paginated data for a specific page.

        Args:
            page_number: Page number to retrieve

        Returns:
            Dictionary with items and pagination metadata
        """
        page = self.paginator.get_page(page_number)

        meta = PaginationMeta(
            current_page=page.number,
            per_page=self.per_page,
            total_items=self.paginator.count,
            total_pages=self.paginator.num_pages,
            has_next=page.has_next(),
            has_previous=page.has_previous(),
            next_page=page.next_page_number() if page.has_next() else None,
            previous_page=page.previous_page_number() if page.has_previous() else None,
            start_index=page.start_index(),
            end_index=page.end_index(),
        )

        return {"items": list(page.object_list), "meta": meta}

    def get_page_with_filters(
        self, page_number: int = 1, applied_filters: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Get paginated data with filter information.

        Args:
            page_number: Page number to retrieve
            applied_filters: Dictionary of applied filters

        Returns:
            Dictionary with items, pagination metadata, and filter info
        """
        result = self.get_page(page_number)
        result["filters_applied"] = applied_filters or {}
        return result


class CursorPaginator:
    """Cursor-based paginator for high-performance pagination."""

    def __init__(
        self,
        queryset: QuerySet,
        ordering_field: str = "id",
        limit: int = 20,
        max_limit: int = 100,
    ):
        """Initialize cursor paginator.

        Args:
            queryset: Django QuerySet to paginate
            ordering_field: Field to use for cursor ordering
            limit: Items per page
            max_limit: Maximum allowed items per page
        """
        self.queryset = queryset
        self.ordering_field = ordering_field
        self.limit = min(limit, max_limit)
        self.max_limit = max_limit

    def get_page(
        self, cursor: str | None = None, reverse: bool = False
    ) -> dict[str, Any]:
        """Get cursor-based paginated data.

        Args:
            cursor: Cursor value for pagination
            reverse: Whether to paginate in reverse direction

        Returns:
            Dictionary with items and cursor pagination metadata
        """
        queryset = self.queryset

        # Apply cursor filtering
        if cursor:
            try:
                cursor_value = self._decode_cursor(cursor)
                if reverse:
                    queryset = queryset.filter(
                        **{f"{self.ordering_field}__lt": cursor_value}
                    )
                else:
                    queryset = queryset.filter(
                        **{f"{self.ordering_field}__gt": cursor_value}
                    )
            except (ValueError, TypeError):
                # Invalid cursor, ignore
                pass

        # Apply ordering
        order_by = f"-{self.ordering_field}" if reverse else self.ordering_field
        queryset = queryset.order_by(order_by)

        # Get one extra item to check if there are more
        items = list(queryset[: self.limit + 1])

        has_more = len(items) > self.limit
        if has_more:
            items = items[: self.limit]

        # Generate cursors
        next_cursor = None
        previous_cursor = None

        if items:
            if not reverse and has_more:
                next_cursor = self._encode_cursor(
                    getattr(items[-1], self.ordering_field)
                )
            if reverse or cursor:
                previous_cursor = self._encode_cursor(
                    getattr(items[0], self.ordering_field)
                )

        meta = CursorPaginationMeta(
            has_next=has_more if not reverse else bool(cursor),
            has_previous=bool(cursor) if not reverse else has_more,
            next_cursor=next_cursor,
            previous_cursor=previous_cursor,
            count=len(items),
        )

        return {"items": items, "meta": meta}

    def _encode_cursor(self, value: Any) -> str:
        """Encode cursor value to string."""
        import base64
        import json

        cursor_data = {"value": str(value), "field": self.ordering_field}
        cursor_json = json.dumps(cursor_data)
        return base64.b64encode(cursor_json.encode()).decode()

    def _decode_cursor(self, cursor: str) -> Any:
        """Decode cursor string to value."""
        import base64
        import json

        cursor_json = base64.b64decode(cursor.encode()).decode()
        cursor_data = json.loads(cursor_json)

        # Convert back to appropriate type
        field = self.queryset.model._meta.get_field(cursor_data["field"])
        value = cursor_data["value"]

        # Handle different field types
        if hasattr(field, "to_python"):
            return field.to_python(value)
        return value


def paginate_queryset(
    queryset: QuerySet,
    page: int = 1,
    per_page: int = 20,
    max_per_page: int = 100,
    applied_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience function to paginate a queryset.

    Args:
        queryset: Django QuerySet to paginate
        page: Page number
        per_page: Items per page
        max_per_page: Maximum items per page
        applied_filters: Applied filter information

    Returns:
        Paginated response dictionary
    """
    paginator = AdvancedPaginator(queryset, per_page, max_per_page)
    return paginator.get_page_with_filters(page, applied_filters)


def cursor_paginate_queryset(
    queryset: QuerySet,
    cursor: str | None = None,
    limit: int = 20,
    ordering_field: str = "id",
    max_limit: int = 100,
    reverse: bool = False,
) -> dict[str, Any]:
    """Convenience function for cursor-based pagination.

    Args:
        queryset: Django QuerySet to paginate
        cursor: Cursor for pagination
        limit: Items per page
        ordering_field: Field to order by
        max_limit: Maximum items per page
        reverse: Reverse pagination direction

    Returns:
        Cursor-paginated response dictionary
    """
    paginator = CursorPaginator(queryset, ordering_field, limit, max_limit)
    return paginator.get_page(cursor, reverse)


# Pagination decorators for views
def paginated_response(
    per_page: int = 20, max_per_page: int = 100, ordering_field: str = "id"
):
    """Decorator to automatically paginate view responses."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get pagination parameters from request
            request = None
            for arg in args:
                if hasattr(arg, "GET"):
                    request = arg
                    break

            if not request:
                return func(*args, **kwargs)

            # Extract pagination params
            page = int(request.GET.get("page", 1))
            requested_per_page = int(request.GET.get("per_page", per_page))
            actual_per_page = min(requested_per_page, max_per_page)

            # Get result from view function
            result = func(*args, **kwargs)

            # Apply pagination if result is a QuerySet
            if isinstance(result, QuerySet):
                return paginate_queryset(result, page, actual_per_page, max_per_page)
            if isinstance(result, tuple) and len(result) == 2:
                status_code, data = result
                if isinstance(data, QuerySet):
                    paginated = paginate_queryset(
                        data, page, actual_per_page, max_per_page
                    )
                    return status_code, paginated

            return result

        return wrapper

    return decorator


def cursor_paginated_response(
    limit: int = 20, max_limit: int = 100, ordering_field: str = "id"
):
    """Decorator for cursor-based pagination."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get pagination parameters from request
            request = None
            for arg in args:
                if hasattr(arg, "GET"):
                    request = arg
                    break

            if not request:
                return func(*args, **kwargs)

            # Extract cursor pagination params
            cursor = request.GET.get("cursor")
            requested_limit = int(request.GET.get("limit", limit))
            actual_limit = min(requested_limit, max_limit)
            reverse = request.GET.get("reverse", "").lower() == "true"

            # Get result from view function
            result = func(*args, **kwargs)

            # Apply cursor pagination if result is a QuerySet
            if isinstance(result, QuerySet):
                return cursor_paginate_queryset(
                    result, cursor, actual_limit, ordering_field, max_limit, reverse
                )
            if isinstance(result, tuple) and len(result) == 2:
                status_code, data = result
                if isinstance(data, QuerySet):
                    paginated = cursor_paginate_queryset(
                        data, cursor, actual_limit, ordering_field, max_limit, reverse
                    )
                    return status_code, paginated

            return result

        return wrapper

    return decorator
