"""Rate limiting decorators for API endpoints."""

import functools
from collections.abc import Callable

from api.throttling.limiter import RateLimiter, RateLimitPresets
from api.utils.http import get_client_ip


def get_rate_limit_key(request, key_type: str = "ip") -> str:
    """Generate rate limit key based on key type.

    Args:
        request: Django request object
        key_type: Type of key - 'ip', 'user', 'session', 'combined'

    Returns:
        str: Rate limit key
    """
    if key_type == "user" and request.user and request.user.is_authenticated:
        return f"user:{request.user.id}"

    if key_type == "session" and hasattr(request, "session"):
        return f"session:{request.session.session_key or 'anonymous'}"

    if key_type == "combined":
        if request.user and request.user.is_authenticated:
            return f"user:{request.user.id}"
        return f"ip:{get_client_ip(request)}"

    # Default to IP
    return f"ip:{get_client_ip(request)}"


def rate_limit(
    rate: int = 100,
    period: int = 60,
    key_type: str = "combined",
    key_prefix: str = "ratelimit",
    methods: list | None = None,
    exempt_staff: bool = True,
):
    """Decorator for rate limiting API endpoints.

    Args:
        rate: Maximum number of requests allowed
        period: Time window in seconds
        key_type: Type of rate limit key ('ip', 'user', 'session', 'combined')
        key_prefix: Prefix for cache keys
        methods: HTTP methods to rate limit (None = all)
        exempt_staff: Whether to exempt staff users

    Usage:
        @rate_limit(rate=10, period=60)
        def my_endpoint(request):
            ...

        @api_controller("/items")
        class ItemController:
            @rate_limit(rate=5, period=60, key_type="user")
            @http_post("/")
            def create_item(self, request):
                ...
    """

    def decorator(func: Callable):
        limiter = RateLimiter(
            key_prefix=key_prefix,
            rate=rate,
            period=period,
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Find request in args or kwargs
            request = kwargs.get("request")
            if request is None:
                # For class-based views, request might be in args
                for arg in args:
                    if hasattr(arg, "META"):
                        request = arg
                        break

            if request is None:
                # Can't rate limit without request, allow through
                return func(*args, **kwargs)

            # Check method filter
            if methods and request.method not in methods:
                return func(*args, **kwargs)

            # Exempt staff users if configured
            if (
                exempt_staff
                and hasattr(request, "user")
                and request.user
                and getattr(request.user, "is_staff", False)
            ):
                return func(*args, **kwargs)

            # Check rate limit
            key = get_rate_limit_key(request, key_type)
            is_allowed, info = limiter.is_allowed(key)

            if not is_allowed:
                return 429, {
                    "error": "Rate limit exceeded",
                    "retry_after": info.get("retry_after", period),
                    "limit": info.get("limit", rate),
                }

            # Add rate limit headers info to request for logging
            if hasattr(request, "META"):
                request.META["X-RateLimit-Limit"] = info.get("limit", rate)
                request.META["X-RateLimit-Remaining"] = info.get("remaining", 0)
                request.META["X-RateLimit-Reset"] = info.get("reset", 0)

            return func(*args, **kwargs)

        return wrapper

    return decorator


# Convenience decorators using presets
def strict_rate_limit(func=None, **kwargs):
    """Apply strict rate limiting (5 req/min)."""
    preset = {**RateLimitPresets.STRICT, **kwargs}
    if func:
        return rate_limit(**preset)(func)
    return rate_limit(**preset)


def standard_rate_limit(func=None, **kwargs):
    """Apply standard rate limiting (100 req/min)."""
    preset = {**RateLimitPresets.STANDARD, **kwargs}
    if func:
        return rate_limit(**preset)(func)
    return rate_limit(**preset)


def auth_rate_limit(func=None, **kwargs):
    """Apply auth rate limiting (10 req/min)."""
    preset = {**RateLimitPresets.AUTH, **kwargs}
    if func:
        return rate_limit(**preset)(func)
    return rate_limit(**preset)


def search_rate_limit(func=None, **kwargs):
    """Apply search rate limiting (30 req/min)."""
    preset = {**RateLimitPresets.SEARCH, **kwargs}
    if func:
        return rate_limit(**preset)(func)
    return rate_limit(**preset)
