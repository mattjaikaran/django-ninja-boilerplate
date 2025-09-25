"""HTTP request utilities."""

from django.http import HttpRequest


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
