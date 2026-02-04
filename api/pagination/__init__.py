"""Advanced pagination utilities for Django Ninja APIs.

This module provides both offset-based and cursor-based pagination.
"""

from api.pagination.cursor import CursorPaginator, cursor_paginate_queryset
from api.pagination.decorators import cursor_paginated_response, paginated_response
from api.pagination.offset import (
    AdvancedPaginator,
    OffsetPaginator,
    paginate_queryset,
)
from api.pagination.schemas import (
    CursorPaginatedResponse,
    CursorPaginationMeta,
    CursorPaginationParams,
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
)

__all__ = [
    "AdvancedPaginator",
    "CursorPaginatedResponse",
    "CursorPaginationMeta",
    "CursorPaginationParams",
    "CursorPaginator",
    "OffsetPaginator",
    "PaginatedResponse",
    "PaginationMeta",
    "PaginationParams",
    "cursor_paginate_queryset",
    "cursor_paginated_response",
    "paginate_queryset",
    "paginated_response",
]
