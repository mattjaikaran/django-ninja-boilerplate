"""Brute force protection via cache-backed attempt tracking."""

import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Max failed attempts before lockout
MAX_ATTEMPTS = 5
# Lockout duration in seconds (15 minutes)
LOCKOUT_SECONDS = 900
# Attempt window in seconds (5 minutes)
ATTEMPT_WINDOW = 300


def _key(identifier: str, prefix: str) -> str:
    hashed = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"bf:{prefix}:{hashed}"


def record_failed_attempt(identifier: str) -> int:
    """Increment failure counter. Returns current attempt count."""
    attempts_key = _key(identifier, "attempts")
    count = cache.get(attempts_key, 0) + 1
    cache.set(attempts_key, count, timeout=ATTEMPT_WINDOW)

    if count >= MAX_ATTEMPTS:
        lockout_key = _key(identifier, "lockout")
        cache.set(lockout_key, True, timeout=LOCKOUT_SECONDS)
        logger.warning(
            "Account locked out after %d failed attempts: %s", count, identifier
        )

    return count


def is_locked_out(identifier: str) -> bool:
    """Return True if this identifier is currently locked out."""
    return bool(cache.get(_key(identifier, "lockout")))


def clear_attempts(identifier: str) -> None:
    """Clear failure counters on successful authentication."""
    cache.delete(_key(identifier, "attempts"))
    cache.delete(_key(identifier, "lockout"))


def remaining_attempts(identifier: str) -> int:
    """Return how many attempts remain before lockout."""
    count = cache.get(_key(identifier, "attempts"), 0)
    return max(0, MAX_ATTEMPTS - count)
