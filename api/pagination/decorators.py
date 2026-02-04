"""Pagination decorators for views."""

from django.db.models import QuerySet

from api.pagination.cursor import cursor_paginate_queryset
from api.pagination.offset import paginate_queryset


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
