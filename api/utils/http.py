"""HTTP request utilities."""

from django.conf import settings
from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str:
    """Return the client IP, trusting only the configured reverse proxies.

    ``TRUSTED_PROXY_COUNT`` (env ``NINJA_NUM_PROXIES``, default 0) is the
    number of proxies that append to ``X-Forwarded-For``. With 0 the header
    is ignored and ``REMOTE_ADDR`` is the client. With N, the client is the
    N-th entry from the right, the address the outermost trusted proxy saw;
    entries further left are client-supplied and never trusted. This matches
    the Ninja Extra throttles (``NINJA_EXTRA["NUM_PROXIES"]``).

    Args:
        request: Django HTTP request object

    Returns:
        Client IP address
    """
    remote_addr = request.META.get("REMOTE_ADDR", "")
    num_proxies = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if num_proxies <= 0 or not x_forwarded_for:
        return remote_addr
    addresses = x_forwarded_for.split(",")
    return addresses[-min(num_proxies, len(addresses))].strip()


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
