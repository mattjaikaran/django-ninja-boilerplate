"""Offset-based pagination utilities."""

from typing import Any

from django.core.paginator import Paginator
from django.db.models import QuerySet

from api.pagination.schemas import PaginationMeta


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
        self, page_number: int = 1, applied_filters: dict[str, Any] | None = None
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


# Alias for clearer naming
OffsetPaginator = AdvancedPaginator


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
