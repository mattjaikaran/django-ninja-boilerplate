"""Redis integration feature generator."""

from .base_generator import BaseGenerator


class RedisGenerator(BaseGenerator):
    """Generator for Redis integration feature."""

    def __init__(
        self,
        app_name: str = "cache",
        minimal: bool = False,
    ):
        """Initialize the Redis generator.

        Args:
            app_name: Name of the Django app to create
            minimal: Whether to generate minimal version
        """
        super().__init__(app_name, minimal)

    def generate(self) -> None:
        """Generate the Redis integration feature."""
        print("Generating Redis integration feature...")

        # Create Django app
        self.create_django_app()

        # Update dependencies
        self._update_dependencies()

        # Generate cache services
        self._generate_cache_services()

        # Generate session manager
        self._generate_session_manager()

        # Generate rate limiting
        self._generate_rate_limiting()

        # Generate cache decorators
        self._generate_cache_decorators()

        # Generate controllers
        self._generate_controllers()

        # Generate tests
        self._generate_tests()

        # Update settings
        self._update_settings()

        print("Redis integration feature generated successfully!")

    def _update_dependencies(self) -> None:
        """Update project dependencies."""
        dependencies = [
            "redis>=5.0.0",
            "django-redis>=5.4.0",
        ]
        if not self.minimal:
            dependencies.extend(
                [
                    "hiredis>=3.0.0",
                    "django-rq>=2.10.0",
                ]
            )
        self.update_pyproject_toml(dependencies)

    def _generate_cache_services(self) -> None:
        """Generate cache services."""
        cache_service_content = '''"""Redis cache service."""

import json
import pickle
from typing import Any, Optional, Union, List
from datetime import datetime, timedelta
import redis
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """Service for Redis cache operations."""

    def __init__(self):
        """Initialize cache service."""
        self.redis_client = self._get_redis_client()

    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client instance."""
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        return redis.from_url(redis_url, decode_responses=True)

    def set(
        self,
        key: str,
        value: Any,
        timeout: Optional[int] = None,
        version: Optional[int] = None,
        serialize: bool = True
    ) -> bool:
        """Set a cache value.

        Args:
            key: Cache key
            value: Value to cache
            timeout: Timeout in seconds (None for no timeout)
            version: Cache version
            serialize: Whether to serialize the value

        Returns:
            True if successful
        """
        try:
            if serialize:
                value = self._serialize_value(value)

            cache.set(key, value, timeout, version)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    def get(
        self,
        key: str,
        default: Any = None,
        version: Optional[int] = None,
        deserialize: bool = True
    ) -> Any:
        """Get a cache value.

        Args:
            key: Cache key
            default: Default value if key not found
            version: Cache version
            deserialize: Whether to deserialize the value

        Returns:
            Cached value or default
        """
        try:
            value = cache.get(key, default, version)
            if value is not None and deserialize and value != default:
                return self._deserialize_value(value)
            return value
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default

    def delete(self, key: str, version: Optional[int] = None) -> bool:
        """Delete a cache value.

        Args:
            key: Cache key to delete
            version: Cache version

        Returns:
            True if successful
        """
        try:
            cache.delete(key, version)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    def get_or_set(
        self,
        key: str,
        default_func: callable,
        timeout: Optional[int] = None,
        version: Optional[int] = None
    ) -> Any:
        """Get cache value or set it using default function.

        Args:
            key: Cache key
            default_func: Function to call if key not found
            timeout: Timeout in seconds
            version: Cache version

        Returns:
            Cached or computed value
        """
        try:
            value = self.get(key, version=version)
            if value is None:
                value = default_func()
                self.set(key, value, timeout, version)
            return value
        except Exception as e:
            logger.error(f"Cache get_or_set error for key {key}: {e}")
            return default_func()

    def get_many(self, keys: List[str], version: Optional[int] = None) -> dict:
        """Get multiple cache values.

        Args:
            keys: List of cache keys
            version: Cache version

        Returns:
            Dictionary of key-value pairs
        """
        try:
            return cache.get_many(keys, version)
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {}

    def set_many(
        self,
        data: dict,
        timeout: Optional[int] = None,
        version: Optional[int] = None
    ) -> bool:
        """Set multiple cache values.

        Args:
            data: Dictionary of key-value pairs
            timeout: Timeout in seconds
            version: Cache version

        Returns:
            True if successful
        """
        try:
            cache.set_many(data, timeout, version)
            return True
        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            return False

    def clear(self) -> bool:
        """Clear all cache.

        Returns:
            True if successful
        """
        try:
            cache.clear()
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    def increment(self, key: str, delta: int = 1, version: Optional[int] = None) -> int:
        """Increment a cache value.

        Args:
            key: Cache key
            delta: Increment amount
            version: Cache version

        Returns:
            New value
        """
        try:
            return cache.get_or_set(key, 0, version=version) + delta
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return delta

    def decrement(self, key: str, delta: int = 1, version: Optional[int] = None) -> int:
        """Decrement a cache value.

        Args:
            key: Cache key
            delta: Decrement amount
            version: Cache version

        Returns:
            New value
        """
        return self.increment(key, -delta, version)

    def expire(self, key: str, timeout: int) -> bool:
        """Set expiration for a key.

        Args:
            key: Cache key
            timeout: Timeout in seconds

        Returns:
            True if successful
        """
        try:
            return self.redis_client.expire(key, timeout)
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False

    def ttl(self, key: str) -> int:
        """Get time to live for a key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds (-1 if no expiry, -2 if key doesn't exist)
        """
        try:
            return self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            return -2

    def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        try:
            return self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    def _serialize_value(self, value: Any) -> str:
        """Serialize value for caching."""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value)
        else:
            return pickle.dumps(value).hex()

    def _deserialize_value(self, value: str) -> Any:
        """Deserialize cached value."""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            try:
                return pickle.loads(bytes.fromhex(value))
            except (ValueError, pickle.UnpicklingError):
                return value


# Global cache service instance
cache_service = CacheService()
'''

        self.create_file(self.app_path / "services" / "__init__.py", "# Cache services")
        self.create_file(
            self.app_path / "services" / "cache_service.py", cache_service_content
        )

    def _generate_session_manager(self) -> None:
        """Generate session manager."""
        session_content = '''"""Redis session manager."""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
from django.contrib.auth import get_user_model

from .cache_service import cache_service

User = get_user_model()


class SessionManager:
    """Manager for Redis-based sessions."""

    SESSION_PREFIX = "session:"
    DEFAULT_TIMEOUT = 3600  # 1 hour

    def create_session(
        self,
        user_id: str,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> str:
        """Create a new session.

        Args:
            user_id: User ID
            data: Additional session data
            timeout: Session timeout in seconds

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        session_data = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "data": data or {}
        }

        key = f"{self.SESSION_PREFIX}{session_id}"
        cache_service.set(
            key,
            session_data,
            timeout or self.DEFAULT_TIMEOUT,
            serialize=False
        )

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found
        """
        key = f"{self.SESSION_PREFIX}{session_id}"
        return cache_service.get(key, deserialize=False)

    def update_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        extend_timeout: bool = True
    ) -> bool:
        """Update session data.

        Args:
            session_id: Session ID
            data: Data to update
            extend_timeout: Whether to extend session timeout

        Returns:
            True if successful
        """
        session_data = self.get_session(session_id)
        if not session_data:
            return False

        session_data["data"].update(data)
        session_data["last_activity"] = datetime.now().isoformat()

        key = f"{self.SESSION_PREFIX}{session_id}"
        timeout = self.DEFAULT_TIMEOUT if extend_timeout else None

        return cache_service.set(
            key,
            session_data,
            timeout,
            serialize=False
        )

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if successful
        """
        key = f"{self.SESSION_PREFIX}{session_id}"
        return cache_service.delete(key)

    def extend_session(
        self,
        session_id: str,
        timeout: Optional[int] = None
    ) -> bool:
        """Extend session timeout.

        Args:
            session_id: Session ID
            timeout: New timeout in seconds

        Returns:
            True if successful
        """
        key = f"{self.SESSION_PREFIX}{session_id}"
        return cache_service.expire(key, timeout or self.DEFAULT_TIMEOUT)

    def get_user_sessions(self, user_id: str) -> list[str]:
        """Get all sessions for a user.

        Args:
            user_id: User ID

        Returns:
            List of session IDs
        """
        # This is a simplified implementation
        # In production, you might want to maintain a user->sessions mapping
        pattern = f"{self.SESSION_PREFIX}*"
        sessions = []

        try:
            for key in cache_service.redis_client.scan_iter(match=pattern):
                session_data = cache_service.get(key.replace(self.SESSION_PREFIX, ""))
                if session_data and session_data.get("user_id") == user_id:
                    sessions.append(key.replace(self.SESSION_PREFIX, ""))
        except Exception:
            pass

        return sessions

    def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of sessions deleted
        """
        sessions = self.get_user_sessions(user_id)
        deleted = 0

        for session_id in sessions:
            if self.delete_session(session_id):
                deleted += 1

        return deleted


# Global session manager instance
session_manager = SessionManager()
'''

        self.create_file(
            self.app_path / "services" / "session_manager.py", session_content
        )

    def _generate_rate_limiting(self) -> None:
        """Generate rate limiting functionality."""
        rate_limit_content = '''"""Redis-based rate limiting."""

import time
from typing import Optional, Tuple
from datetime import datetime, timedelta

from .cache_service import cache_service


class RateLimiter:
    """Redis-based rate limiter."""

    def __init__(self, key_prefix: str = "rate_limit:"):
        """Initialize rate limiter.

        Args:
            key_prefix: Prefix for cache keys
        """
        self.key_prefix = key_prefix

    def is_allowed(
        self,
        identifier: str,
        limit: int,
        window: int,
        cost: int = 1
    ) -> Tuple[bool, dict]:
        """Check if request is allowed under rate limit.

        Args:
            identifier: Unique identifier (user ID, IP, etc.)
            limit: Maximum requests allowed
            window: Time window in seconds
            cost: Cost of this request (default 1)

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        key = f"{self.key_prefix}{identifier}"
        now = int(time.time())

        # Use sliding window counter
        with cache_service.redis_client.pipeline() as pipe:
            pipe.multi()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, now - window)

            # Count current requests
            pipe.zcard(key)

            # Add current request if allowed
            current_count = pipe.execute()[1]

            if current_count + cost <= limit:
                # Add request
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, window)
                pipe.execute()

                return True, {
                    "allowed": True,
                    "limit": limit,
                    "remaining": limit - current_count - cost,
                    "reset_time": now + window,
                    "retry_after": None
                }
            else:
                # Get oldest entry for retry_after calculation
                oldest = cache_service.redis_client.zrange(key, 0, 0, withscores=True)
                retry_after = int(oldest[0][1]) + window - now if oldest else window

                return False, {
                    "allowed": False,
                    "limit": limit,
                    "remaining": 0,
                    "reset_time": now + window,
                    "retry_after": retry_after
                }

    def reset(self, identifier: str) -> bool:
        """Reset rate limit for identifier.

        Args:
            identifier: Unique identifier

        Returns:
            True if successful
        """
        key = f"{self.key_prefix}{identifier}"
        return cache_service.delete(key)

    def get_usage(self, identifier: str, window: int) -> dict:
        """Get current usage for identifier.

        Args:
            identifier: Unique identifier
            window: Time window in seconds

        Returns:
            Usage information
        """
        key = f"{self.key_prefix}{identifier}"
        now = int(time.time())

        # Clean old entries and count
        cache_service.redis_client.zremrangebyscore(key, 0, now - window)
        current_count = cache_service.redis_client.zcard(key)

        return {
            "current_count": current_count,
            "window_start": now - window,
            "window_end": now
        }


# Rate limiting decorators
def rate_limit(identifier_func: callable, limit: int, window: int):
    """Decorator for rate limiting.

    Args:
        identifier_func: Function to get identifier from request
        limit: Request limit
        window: Time window in seconds
    """
    def decorator(func):
        def wrapper(self, request, *args, **kwargs):
            limiter = RateLimiter()
            identifier = identifier_func(request)

            allowed, info = limiter.is_allowed(identifier, limit, window)

            if not allowed:
                from ninja_extra.exceptions import APIException
                raise APIException(
                    f"Rate limit exceeded. Try again in {info['retry_after']} seconds.",
                    429
                )

            # Add rate limit headers to response
            response = func(self, request, *args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
                response.headers['X-RateLimit-Reset'] = str(info['reset_time'])

            return response
        return wrapper
    return decorator


def get_client_ip(request):
    """Get client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_id(request):
    """Get user ID from request."""
    if hasattr(request, 'user') and request.user.is_authenticated:
        return str(request.user.id)
    return get_client_ip(request)


# Global rate limiter instance
rate_limiter = RateLimiter()
'''

        self.create_file(
            self.app_path / "services" / "rate_limiter.py", rate_limit_content
        )

    def _generate_cache_decorators(self) -> None:
        """Generate cache decorators."""
        decorators_content = '''"""Cache decorators for views and functions."""

import hashlib
import json
from functools import wraps
from typing import Callable, Optional, Any

from .services.cache_service import cache_service


def cache_result(
    timeout: int = 300,
    key_func: Optional[Callable] = None,
    version: Optional[int] = None
):
    """Decorator to cache function results.

    Args:
        timeout: Cache timeout in seconds
        key_func: Function to generate cache key
        version: Cache version
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                key_data = {
                    'func': func.__name__,
                    'args': str(args),
                    'kwargs': str(sorted(kwargs.items()))
                }
                cache_key = hashlib.md5(
                    json.dumps(key_data, sort_keys=True).encode()
                ).hexdigest()

            # Try to get from cache
            result = cache_service.get(cache_key, version=version)
            if result is not None:
                return result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, timeout, version)

            return result
        return wrapper
    return decorator


def cache_view(
    timeout: int = 300,
    key_func: Optional[Callable] = None,
    per_user: bool = False
):
    """Decorator to cache view responses.

    Args:
        timeout: Cache timeout in seconds
        key_func: Function to generate cache key
        per_user: Whether to cache per user
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(request, *args, **kwargs)
            else:
                key_parts = [
                    func.__name__,
                    request.path,
                    str(sorted(request.GET.items())),
                ]

                if per_user and hasattr(request, 'user') and request.user.is_authenticated:
                    key_parts.append(f"user:{request.user.id}")

                cache_key = hashlib.md5(
                    "|".join(key_parts).encode()
                ).hexdigest()

            # Try to get from cache
            cached_response = cache_service.get(f"view:{cache_key}")
            if cached_response is not None:
                return cached_response

            # Execute view and cache response
            response = func(self, request, *args, **kwargs)
            cache_service.set(f"view:{cache_key}", response, timeout)

            return response
        return wrapper
    return decorator


def invalidate_cache(*cache_keys: str):
    """Decorator to invalidate cache keys after function execution.

    Args:
        cache_keys: Cache keys to invalidate
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Invalidate cache keys
            for key in cache_keys:
                cache_service.delete(key)

            return result
        return wrapper
    return decorator


def cache_unless(condition_func: Callable):
    """Decorator to conditionally skip caching.

    Args:
        condition_func: Function that returns True to skip caching
    """
    def decorator(cache_decorator):
        def wrapper(func):
            cached_func = cache_decorator(func)

            @wraps(func)
            def inner(*args, **kwargs):
                if condition_func(*args, **kwargs):
                    return func(*args, **kwargs)
                return cached_func(*args, **kwargs)
            return inner
        return wrapper
    return decorator
'''

        self.create_file(self.app_path / "decorators.py", decorators_content)

    def _generate_controllers(self) -> None:
        """Generate cache management controllers."""
        controllers_content = f'''"""Cache management controllers."""

import logging
from typing import Dict, Any
from ninja_extra import api_controller, http_delete, http_get, http_post

from {self.app_name}.services.cache_service import cache_service
from {self.app_name}.services.session_manager import session_manager
from {self.app_name}.services.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


@api_controller("/cache", tags=["Cache Management"])
class CacheController:
    """Cache management controller."""

    @http_get("/stats", response={{200: dict, 400: dict}})
    def get_cache_stats(self, request):
        """Get cache statistics."""
        try:
            # Basic Redis info
            info = cache_service.redis_client.info()

            stats = {{
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
            }}

            # Calculate hit ratio
            hits = stats["keyspace_hits"]
            misses = stats["keyspace_misses"]
            if hits + misses > 0:
                stats["hit_ratio"] = hits / (hits + misses)
            else:
                stats["hit_ratio"] = 0

            return 200, stats
        except Exception as e:
            logger.error(f"Error getting cache stats: {{e}}")
            return 400, {{"error": str(e)}}

    @http_get("/key/{{str:key}}", response={{200: dict, 400: dict, 404: dict}})
    def get_cache_key(self, request, key: str):
        """Get cache key information."""
        try:
            if not cache_service.exists(key):
                return 404, {{"error": "Key not found"}}

            value = cache_service.get(key, deserialize=False)
            ttl = cache_service.ttl(key)

            return 200, {{
                "key": key,
                "value": str(value)[:100] + "..." if len(str(value)) > 100 else str(value),
                "ttl": ttl,
                "exists": True,
            }}
        except Exception as e:
            logger.error(f"Error getting cache key {{key}}: {{e}}")
            return 400, {{"error": str(e)}}

    @http_delete("/key/{{str:key}}", response={{204: dict, 400: dict}})
    def delete_cache_key(self, request, key: str):
        """Delete a cache key."""
        try:
            success = cache_service.delete(key)
            if success:
                return 204, {{"message": "Key deleted successfully"}}
            else:
                return 400, {{"error": "Failed to delete key"}}
        except Exception as e:
            logger.error(f"Error deleting cache key {{key}}: {{e}}")
            return 400, {{"error": str(e)}}

    @http_post("/clear", response={{200: dict, 400: dict}})
    def clear_cache(self, request):
        """Clear all cache."""
        try:
            success = cache_service.clear()
            if success:
                return 200, {{"message": "Cache cleared successfully"}}
            else:
                return 400, {{"error": "Failed to clear cache"}}
        except Exception as e:
            logger.error(f"Error clearing cache: {{e}}")
            return 400, {{"error": str(e)}}

    @http_get("/sessions/user/{{str:user_id}}", response={{200: list, 400: dict}})
    def get_user_sessions(self, request, user_id: str):
        """Get sessions for a user."""
        try:
            sessions = session_manager.get_user_sessions(user_id)
            return 200, sessions
        except Exception as e:
            logger.error(f"Error getting user sessions: {{e}}")
            return 400, {{"error": str(e)}}

    @http_delete("/sessions/user/{{str:user_id}}", response={{200: dict, 400: dict}})
    def delete_user_sessions(self, request, user_id: str):
        """Delete all sessions for a user."""
        try:
            deleted = session_manager.delete_user_sessions(user_id)
            return 200, {{"message": f"Deleted {{deleted}} sessions"}}
        except Exception as e:
            logger.error(f"Error deleting user sessions: {{e}}")
            return 400, {{"error": str(e)}}

    @http_get("/rate-limit/{{str:identifier}}", response={{200: dict, 400: dict}})
    def get_rate_limit_usage(self, request, identifier: str):
        """Get rate limit usage for identifier."""
        try:
            usage = rate_limiter.get_usage(identifier, 3600)  # 1 hour window
            return 200, usage
        except Exception as e:
            logger.error(f"Error getting rate limit usage: {{e}}")
            return 400, {{"error": str(e)}}

    @http_delete("/rate-limit/{{str:identifier}}", response={{200: dict, 400: dict}})
    def reset_rate_limit(self, request, identifier: str):
        """Reset rate limit for identifier."""
        try:
            success = rate_limiter.reset(identifier)
            if success:
                return 200, {{"message": "Rate limit reset successfully"}}
            else:
                return 400, {{"error": "Failed to reset rate limit"}}
        except Exception as e:
            logger.error(f"Error resetting rate limit: {{e}}")
            return 400, {{"error": str(e)}}
'''

        self.create_file(
            self.app_path / "controllers" / "cache_controller.py", controllers_content
        )

    def _generate_tests(self) -> None:
        """Generate Redis tests."""
        tests_content = f'''"""Redis cache tests."""

import pytest
import time
from unittest.mock import patch, MagicMock

from {self.app_name}.services.cache_service import CacheService
from {self.app_name}.services.session_manager import SessionManager
from {self.app_name}.services.rate_limiter import RateLimiter


@pytest.fixture
def cache_service():
    return CacheService()


@pytest.fixture
def session_manager():
    return SessionManager()


@pytest.fixture
def rate_limiter():
    return RateLimiter()


@pytest.mark.django_db
class TestCacheService:
    def test_set_and_get_string(self, cache_service):
        key = "test_string"
        value = "test_value"

        assert cache_service.set(key, value)
        assert cache_service.get(key) == value

    def test_set_and_get_dict(self, cache_service):
        key = "test_dict"
        value = {{"name": "test", "age": 25}}

        assert cache_service.set(key, value)
        retrieved = cache_service.get(key)
        assert retrieved == value

    def test_get_nonexistent_key(self, cache_service):
        assert cache_service.get("nonexistent") is None
        assert cache_service.get("nonexistent", "default") == "default"

    def test_delete_key(self, cache_service):
        key = "test_delete"
        value = "test_value"

        cache_service.set(key, value)
        assert cache_service.get(key) == value

        assert cache_service.delete(key)
        assert cache_service.get(key) is None

    def test_get_or_set(self, cache_service):
        key = "test_get_or_set"

        def default_func():
            return "computed_value"

        # First call should compute and cache
        result = cache_service.get_or_set(key, default_func)
        assert result == "computed_value"

        # Second call should return cached value
        def new_func():
            return "new_value"

        result = cache_service.get_or_set(key, new_func)
        assert result == "computed_value"  # Should be cached value

    def test_set_many_and_get_many(self, cache_service):
        data = {{
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }}

        assert cache_service.set_many(data)
        retrieved = cache_service.get_many(list(data.keys()))

        for key, value in data.items():
            assert retrieved[key] == value

    @patch('cache.services.cache_service.cache_service.redis_client')
    def test_increment(self, mock_redis, cache_service):
        key = "test_counter"

        # Mock the get_or_set behavior
        cache_service.set(key, 0)

        result = cache_service.increment(key, 1)
        assert result == 1

    def test_exists(self, cache_service):
        key = "test_exists"

        # Key doesn't exist initially
        assert not cache_service.exists(key)

        # Set key and check again
        cache_service.set(key, "value")
        assert cache_service.exists(key)


@pytest.mark.django_db
class TestSessionManager:
    def test_create_session(self, session_manager, test_user):
        session_id = session_manager.create_session(str(test_user.id))

        assert session_id is not None
        assert len(session_id) == 36  # UUID4 length

        session_data = session_manager.get_session(session_id)
        assert session_data["user_id"] == str(test_user.id)

    def test_update_session(self, session_manager, test_user):
        session_id = session_manager.create_session(str(test_user.id))

        update_data = {{"key": "value", "count": 1}}
        assert session_manager.update_session(session_id, update_data)

        session_data = session_manager.get_session(session_id)
        assert session_data["data"]["key"] == "value"
        assert session_data["data"]["count"] == 1

    def test_delete_session(self, session_manager, test_user):
        session_id = session_manager.create_session(str(test_user.id))

        # Session exists
        assert session_manager.get_session(session_id) is not None

        # Delete session
        assert session_manager.delete_session(session_id)

        # Session no longer exists
        assert session_manager.get_session(session_id) is None

    def test_get_nonexistent_session(self, session_manager):
        assert session_manager.get_session("nonexistent") is None


@pytest.mark.django_db
class TestRateLimiter:
    def test_rate_limit_allowed(self, rate_limiter):
        identifier = "test_user"
        limit = 5
        window = 60

        # First request should be allowed
        allowed, info = rate_limiter.is_allowed(identifier, limit, window)
        assert allowed
        assert info["remaining"] == limit - 1

    def test_rate_limit_exceeded(self, rate_limiter):
        identifier = "test_user_limit"
        limit = 2
        window = 60

        # First two requests should be allowed
        for i in range(2):
            allowed, info = rate_limiter.is_allowed(identifier, limit, window)
            assert allowed

        # Third request should be denied
        allowed, info = rate_limiter.is_allowed(identifier, limit, window)
        assert not allowed
        assert info["remaining"] == 0
        assert info["retry_after"] > 0

    def test_rate_limit_reset(self, rate_limiter):
        identifier = "test_user_reset"
        limit = 1
        window = 60

        # Use up the limit
        rate_limiter.is_allowed(identifier, limit, window)
        allowed, info = rate_limiter.is_allowed(identifier, limit, window)
        assert not allowed

        # Reset and try again
        assert rate_limiter.reset(identifier)
        allowed, info = rate_limiter.is_allowed(identifier, limit, window)
        assert allowed

    def test_rate_limit_usage(self, rate_limiter):
        identifier = "test_user_usage"
        window = 60

        # Make some requests
        rate_limiter.is_allowed(identifier, 10, window)
        rate_limiter.is_allowed(identifier, 10, window)

        usage = rate_limiter.get_usage(identifier, window)
        assert usage["current_count"] == 2


@pytest.mark.django_db
class TestCacheAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client
        return Client()

    def test_get_cache_stats(self, api_client, auth_headers):
        response = api_client.get("/api/cache/stats", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "connected_clients" in data
        assert "used_memory" in data

    def test_cache_key_operations(self, api_client, auth_headers, cache_service):
        # Set a test key
        test_key = "api_test_key"
        cache_service.set(test_key, "test_value")

        # Get key info
        response = api_client.get(f"/api/cache/key/{{test_key}}", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == test_key
        assert data["exists"]

        # Delete key
        response = api_client.delete(f"/api/cache/key/{{test_key}}", **auth_headers)
        assert response.status_code == 204

        # Verify key is deleted
        response = api_client.get(f"/api/cache/key/{{test_key}}", **auth_headers)
        assert response.status_code == 404
'''

        self.create_file(self.app_path / "tests" / "test_cache.py", tests_content)

    def _update_settings(self) -> None:
        """Update Django settings for Redis."""
        settings_updates = {
            "REDIS_URL": "redis://localhost:6379/0",
            "CACHES": {
                "default": {
                    "BACKEND": "django_redis.cache.RedisCache",
                    "LOCATION": "redis://127.0.0.1:6379/1",
                    "OPTIONS": {
                        "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    },
                }
            },
            "SESSION_ENGINE": "django.contrib.sessions.backends.cache",
            "SESSION_CACHE_ALIAS": "default",
        }
        self.update_settings(self.app_name, settings_updates)
