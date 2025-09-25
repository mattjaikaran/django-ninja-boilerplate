"""API utilities module.

This module provides common utility functions and helpers used across the django-ninja-boilerplate API.
"""

from typing import Any

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import HttpRequest

from .config.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


def get_client_ip(request: HttpRequest) -> str:
    """Get the client IP address from the request.

    Args:
        request: Django HTTP request object

    Returns:
        Client IP address
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def is_ajax(request: HttpRequest) -> bool:
    """Check if the request is an AJAX request.

    Args:
        request: Django HTTP request object

    Returns:
        True if request is AJAX, False otherwise
    """
    return request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"


def get_user_agent(request: HttpRequest) -> str:
    """Get user agent string from request.

    Args:
        request: Django HTTP request object

    Returns:
        User agent string
    """
    return request.META.get("HTTP_USER_AGENT", "")


def is_mobile_request(request: HttpRequest) -> bool:
    """Check if request is from a mobile device.

    Args:
        request: Django HTTP request object

    Returns:
        True if request is from mobile device, False otherwise
    """
    user_agent = get_user_agent(request).lower()
    mobile_keywords = [
        "mobile",
        "android",
        "iphone",
        "ipad",
        "ipod",
        "blackberry",
        "windows phone",
        "opera mini",
        "iemobile",
        "symbian",
    ]
    return any(keyword in user_agent for keyword in mobile_keywords)


def get_request_protocol(request: HttpRequest) -> str:
    """Get request protocol (http or https).

    Args:
        request: Django HTTP request object

    Returns:
        Protocol string
    """
    return "https" if request.is_secure() else "http"


def build_absolute_uri(request: HttpRequest, path: str = "") -> str:
    """Build absolute URI for given path.

    Args:
        request: Django HTTP request object
        path: Path to append to base URL

    Returns:
        Absolute URI
    """
    return request.build_absolute_uri(path)


def paginate_queryset(
    queryset: QuerySet,
    page: int = 1,
    page_size: int | None = None,
) -> dict[str, Any]:
    """Paginate a queryset and return pagination info.

    Args:
        queryset: Django queryset to paginate
        page: Page number to retrieve (default: 1)
        page_size: Number of items per page (default from constants)

    Returns:
        Dictionary containing paginated results and pagination metadata
    """
    if page_size is None:
        page_size = DEFAULT_PAGE_SIZE

    # Ensure page_size doesn't exceed maximum
    page_size = min(page_size, MAX_PAGE_SIZE)

    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)

    return {
        "results": page_obj.object_list,
        "pagination": {
            "page": page_obj.number,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "total_count": paginator.count,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
            "previous_page": page_obj.previous_page_number()
            if page_obj.has_previous()
            else None,
        },
    }


def get_page_range(current_page: int, total_pages: int, window: int = 5) -> list[int]:
    """Get a range of page numbers around the current page.

    Args:
        current_page: Current page number
        total_pages: Total number of pages
        window: Number of pages to show around current page

    Returns:
        List of page numbers to display
    """
    start = max(1, current_page - window // 2)
    end = min(total_pages + 1, start + window)
    start = max(1, end - window)

    return list(range(start, end))
