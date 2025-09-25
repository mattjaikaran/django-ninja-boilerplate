from collections.abc import Callable
from functools import wraps
from typing import Any

from django.core.cache import cache
from ninja.responses import Response

from .settings import CACHE_TTL, cache_key_prefix


def cached_view(timeout: int | None = CACHE_TTL, key_prefix: str = "view"):
    """Cache decorator for API views.
    Usage:
        @http_get('')
        @cached_view(timeout=300, key_prefix='products')
        def list_products(self):
            ...
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped_view(
            controller_self: Any, request: Any = None, *args: Any, **kwargs: Any
        ) -> Any:
            # Generate cache key based on the full URL path and query parameters
            if request and hasattr(request, "get_full_path"):
                cache_key = f"{key_prefix}:{request.get_full_path()}"
            else:
                # If no request object, use args and kwargs for key
                cache_key = f"{key_prefix}:{':'.join(map(str, args))}"
                if kwargs:
                    cache_key += (
                        f":{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
                    )

            # Try to get from cache
            response = cache.get(cache_key_prefix(cache_key))

            if response is None:
                # Generate response
                response = view_func(controller_self, *args, **kwargs)

                # Only cache Response objects
                if isinstance(response, (Response, dict, list)):
                    cache.set(cache_key_prefix(cache_key), response, timeout)

            return response

        return _wrapped_view

    return decorator


def cached_method(timeout: int | None = CACHE_TTL, key_prefix: str = "method"):
    """Cache decorator for class methods.
    Usage:
        @cached_method(timeout=300, key_prefix='user')
        def get_user_data(self, user_id):
            ...
    """

    def decorator(method: Callable) -> Callable:
        @wraps(method)
        def _wrapped_method(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Generate cache key based on method arguments
            cache_key = f"{key_prefix}:{':'.join(map(str, args))}"
            if kwargs:
                cache_key += (
                    f":{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
                )

            result = cache.get(cache_key_prefix(cache_key))

            if result is None:
                result = method(self, *args, **kwargs)
                if result is not None:  # Don't cache None values
                    cache.set(cache_key_prefix(cache_key), result, timeout)

            return result

        return _wrapped_method

    return decorator
