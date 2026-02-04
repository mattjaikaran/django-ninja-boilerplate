"""Throttling and rate limiting utilities for Django Ninja.

This module provides rate limiting decorators and classes for API endpoints,
compatible with Django Ninja and Django Ninja Extra.
"""

from api.throttling.decorators import (
    auth_rate_limit,
    get_rate_limit_key,
    rate_limit,
    search_rate_limit,
    standard_rate_limit,
    strict_rate_limit,
)
from api.throttling.limiter import (
    RateLimiter,
    RateLimitExceeded,
    RateLimitPresets,
    SlidingWindowRateLimiter,
    TokenBucketRateLimiter,
    auth_limiter,
    default_limiter,
    upload_limiter,
)

__all__ = [
    "RateLimitExceeded",
    "RateLimitPresets",
    "RateLimiter",
    "SlidingWindowRateLimiter",
    "TokenBucketRateLimiter",
    "auth_limiter",
    "auth_rate_limit",
    "default_limiter",
    "get_rate_limit_key",
    "rate_limit",
    "search_rate_limit",
    "standard_rate_limit",
    "strict_rate_limit",
    "upload_limiter",
]
