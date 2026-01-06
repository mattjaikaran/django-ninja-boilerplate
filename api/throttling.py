"""Throttling and rate limiting utilities for Django Ninja.

This module provides rate limiting decorators and classes for API endpoints,
compatible with Django Ninja and Django Ninja Extra.
"""

import functools
import logging
import time
from collections.abc import Callable

from django.core.cache import cache

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)


class RateLimiter:
    """Token bucket rate limiter using Redis/cache backend.

    Provides flexible rate limiting with configurable limits and windows.
    """

    def __init__(
        self,
        key_prefix: str = "ratelimit",
        rate: int = 100,
        period: int = 60,
        cache_backend: str = "default",
    ):
        """Initialize the rate limiter.

        Args:
            key_prefix: Prefix for cache keys
            rate: Maximum number of requests allowed
            period: Time window in seconds
            cache_backend: Cache backend to use
        """
        self.key_prefix = key_prefix
        self.rate = rate
        self.period = period
        self.cache_backend = cache_backend

    def _get_cache_key(self, identifier: str) -> str:
        """Generate cache key for identifier."""
        return f"{self.key_prefix}:{identifier}"

    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """Check if request is allowed.

        Args:
            identifier: Unique identifier (user ID, IP, etc.)

        Returns:
            tuple: (is_allowed, info_dict)
        """
        cache_key = self._get_cache_key(identifier)
        now = time.time()

        try:
            # Get current window data
            data = cache.get(cache_key)

            if data is None:
                # First request in window
                data = {"count": 1, "start": now}
                cache.set(cache_key, data, self.period)
                return True, {
                    "limit": self.rate,
                    "remaining": self.rate - 1,
                    "reset": int(now + self.period),
                }

            # Check if window expired
            if now - data["start"] >= self.period:
                # New window
                data = {"count": 1, "start": now}
                cache.set(cache_key, data, self.period)
                return True, {
                    "limit": self.rate,
                    "remaining": self.rate - 1,
                    "reset": int(now + self.period),
                }

            # Check rate limit
            if data["count"] >= self.rate:
                retry_after = int(self.period - (now - data["start"]))
                return False, {
                    "limit": self.rate,
                    "remaining": 0,
                    "reset": int(data["start"] + self.period),
                    "retry_after": retry_after,
                }

            # Increment counter
            data["count"] += 1
            remaining_time = int(self.period - (now - data["start"]))
            cache.set(cache_key, data, remaining_time)

            return True, {
                "limit": self.rate,
                "remaining": self.rate - data["count"],
                "reset": int(data["start"] + self.period),
            }

        except Exception as e:
            logger.warning("Rate limiter error: %s", e)
            # Fail open - allow request if cache fails
            return True, {"limit": self.rate, "remaining": 0, "reset": 0}

    def reset(self, identifier: str) -> None:
        """Reset rate limit for identifier."""
        cache_key = self._get_cache_key(identifier)
        cache.delete(cache_key)


def get_client_ip(request) -> str:
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return ip


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


# Predefined rate limiters for common use cases
class RateLimitPresets:
    """Predefined rate limit configurations."""

    # Very strict - for sensitive operations
    STRICT = {"rate": 5, "period": 60}

    # Standard - for regular API endpoints
    STANDARD = {"rate": 100, "period": 60}

    # Relaxed - for read-heavy endpoints
    RELAXED = {"rate": 300, "period": 60}

    # Auth - for authentication endpoints
    AUTH = {"rate": 10, "period": 60}

    # Search - for search endpoints
    SEARCH = {"rate": 30, "period": 60}

    # Upload - for file upload endpoints
    UPLOAD = {"rate": 10, "period": 300}

    # Bulk - for bulk operation endpoints
    BULK = {"rate": 5, "period": 60}


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


# Sliding window rate limiter (more accurate)
class SlidingWindowRateLimiter:
    """Sliding window rate limiter for more accurate limiting.

    Uses a sliding window algorithm for smoother rate limiting
    compared to fixed windows.
    """

    def __init__(
        self,
        key_prefix: str = "sliding_ratelimit",
        rate: int = 100,
        period: int = 60,
    ):
        self.key_prefix = key_prefix
        self.rate = rate
        self.period = period

    def _get_cache_key(self, identifier: str) -> str:
        return f"{self.key_prefix}:{identifier}"

    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """Check if request is allowed using sliding window."""
        cache_key = self._get_cache_key(identifier)
        now = time.time()
        window_start = now - self.period

        try:
            # Get request timestamps
            timestamps = cache.get(cache_key, [])

            # Remove timestamps outside window
            timestamps = [ts for ts in timestamps if ts > window_start]

            # Check limit
            if len(timestamps) >= self.rate:
                oldest = min(timestamps)
                retry_after = int(oldest + self.period - now)
                return False, {
                    "limit": self.rate,
                    "remaining": 0,
                    "retry_after": max(1, retry_after),
                }

            # Add new timestamp
            timestamps.append(now)
            cache.set(cache_key, timestamps, self.period + 1)

            return True, {
                "limit": self.rate,
                "remaining": self.rate - len(timestamps),
            }

        except Exception as e:
            logger.warning("Sliding rate limiter error: %s", e)
            return True, {"limit": self.rate, "remaining": 0}


# Global rate limiter instances for reuse
default_limiter = RateLimiter(rate=100, period=60)
auth_limiter = RateLimiter(key_prefix="auth_ratelimit", rate=10, period=60)
upload_limiter = RateLimiter(key_prefix="upload_ratelimit", rate=10, period=300)
