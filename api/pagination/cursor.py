"""Cursor-based pagination utilities."""

import base64
import json
from typing import Any

from django.db.models import QuerySet

from api.pagination.schemas import CursorPaginationMeta


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
        cursor_data = {"value": str(value), "field": self.ordering_field}
        cursor_json = json.dumps(cursor_data)
        return base64.b64encode(cursor_json.encode()).decode()

    def _decode_cursor(self, cursor: str) -> Any:
        """Decode cursor string to value."""
        cursor_json = base64.b64decode(cursor.encode()).decode()
        cursor_data = json.loads(cursor_json)

        # Convert back to appropriate type
        field = self.queryset.model._meta.get_field(cursor_data["field"])
        value = cursor_data["value"]

        # Handle different field types
        if hasattr(field, "to_python"):
            return field.to_python(value)
        return value


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
