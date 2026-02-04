"""Rate limiter classes for API throttling."""

import logging
import time

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


# Alias for clearer naming
TokenBucketRateLimiter = RateLimiter


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


# Global rate limiter instances for reuse
default_limiter = RateLimiter(rate=100, period=60)
auth_limiter = RateLimiter(key_prefix="auth_ratelimit", rate=10, period=60)
upload_limiter = RateLimiter(key_prefix="upload_ratelimit", rate=10, period=300)
