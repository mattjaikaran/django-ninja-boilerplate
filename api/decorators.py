"""Comprehensive decorator system for the django-ninja-boilerplate API.

This module provides a complete set of decorators for error handling, logging,
permissions, caching, pagination, and database optimizations.
"""

import functools
import logging
import time
from collections.abc import Callable

from django.core.cache import cache
from django.db import models
from django.db.models import Q, QuerySet
from django.http import HttpRequest

from .config.constants import CACHE_TIMEOUT_MEDIUM, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from .exceptions import (
    APIPermissionError,
    AuthenticationError,
    BaseAPIException,
    NotFoundError,
    ValidationError,
)
from .pagination import paginate_queryset
from .permissions import (
    IsAdminUser,
    can_modify_object,
)
from .utils import get_client_ip

# Configure logging
logger = logging.getLogger(__name__)

# Constants for response status codes
HTTP_OK = 200
TUPLE_RESPONSE_LENGTH = 2


def handle_exceptions(func: Callable) -> Callable:
    """Comprehensive exception handler decorator.

    Handles all exceptions and returns appropriate HTTP responses
    without exposing internal details in production.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseAPIException as e:
            logger.warning("API Exception in %s: %s", func.__name__, e.message)
            return e.status_code, e.to_dict()
        except models.ObjectDoesNotExist:
            error = NotFoundError("Resource not found")
            return error.status_code, error.to_dict()
        except ValidationError as e:
            logger.warning("Validation error in %s: %s", func.__name__, e)
            return e.status_code, e.to_dict()
        except Exception:
            logger.exception("Unhandled exception in %s", func.__name__)
            error = BaseAPIException("An internal error occurred")
            return error.status_code, error.to_dict()

    return wrapper


def log_api_call(
    include_request_data: bool = False,
    include_response_data: bool = False,
    log_level: int = logging.INFO,
) -> Callable:
    """API call logging decorator.

    Args:
        include_request_data: Whether to log request payload
        include_response_data: Whether to log response data
        log_level: Logging level to use
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            # Extract request info
            request = None
            for arg in args:
                if hasattr(arg, "META") and hasattr(arg, "method"):
                    request = arg
                    break
                if hasattr(arg, "request"):
                    request = arg.request
                    break

            # Log request
            if request:
                client_ip = get_client_ip(request)
                user = getattr(request, "user", None)
                user_info = f"user={user.username if user and user.is_authenticated else 'anonymous'}"

                log_message = (
                    f"API Call: {func.__name__} | {user_info} | IP={client_ip}"
                )

                if include_request_data and hasattr(request, "data"):
                    log_message += f" | Request: {request.data}"

                logger.log(log_level, log_message)

            # Execute function
            try:
                result = func(*args, **kwargs)
            except Exception:
                execution_time = time.time() - start_time
                logger.exception(
                    "API Error: %s | Time=%.3fs", func.__name__, execution_time
                )
                raise
            else:
                # Log response
                execution_time = time.time() - start_time
                log_message = (
                    f"API Success: {func.__name__} | Time={execution_time:.3f}s"
                )

                if include_response_data:
                    log_message += f" | Response: {result}"

                logger.log(log_level, log_message)

                return result

        return wrapper

    return decorator


def require_authentication(func: Callable) -> Callable:
    """Require user to be authenticated."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Find request object
        request = None
        for arg in args:
            if hasattr(arg, "user") and hasattr(arg, "META"):
                request = arg
                break
            if hasattr(arg, "request"):
                request = arg.request
                break

        if not request or not request.user or not request.user.is_authenticated:
            auth_error = AuthenticationError("Authentication required")
            raise auth_error

        return func(*args, **kwargs)

    return wrapper


def require_permissions(*permission_classes) -> Callable:
    """Require specific permissions.

    Args:
        *permission_classes: Permission classes to check (e.g., IsAdminUser, IsOwnerOrAdmin)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @require_authentication
        def wrapper(*args, **kwargs):
            # Find request object
            request = None
            for arg in args:
                if hasattr(arg, "user") and hasattr(arg, "META"):
                    request = arg
                    break
                if hasattr(arg, "request"):
                    request = arg.request
                    break

            if not request:
                perm_error = APIPermissionError("Request object not found")
                raise perm_error

            # Check permissions
            for permission_class in permission_classes:
                permission = permission_class()
                if not permission.has_permission(request, None):
                    perm_error = APIPermissionError(
                        f"Permission denied: {permission_class.__name__}"
                    )
                    raise perm_error

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_admin(func: Callable) -> Callable:
    """Require user to be admin."""
    return require_permissions(IsAdminUser)(func)


def require_owner_or_admin(obj_param: str = "obj") -> Callable:
    """Require user to be owner of object or admin.

    Args:
        obj_param: Name of the parameter containing the object to check ownership
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @require_authentication
        def wrapper(*args, **kwargs):
            # Find request object
            request = None
            for arg in args:
                if hasattr(arg, "user") and hasattr(arg, "META"):
                    request = arg
                    break
                if hasattr(arg, "request"):
                    request = arg.request
                    break

            if not request:
                perm_error = APIPermissionError("Request object not found")
                raise perm_error

            # Get object
            obj = kwargs.get(obj_param)
            if not obj:
                not_found_error = NotFoundError("Object not found")
                raise not_found_error

            # Check if user can modify object
            if not can_modify_object(request.user, obj):
                perm_error = APIPermissionError("Access denied: You are not the owner")
                raise perm_error

            return func(*args, **kwargs)

        return wrapper

    return decorator


def optimize_queryset(**optimizations) -> Callable:
    """Database optimization decorator.

    Args:
        **optimizations: Optimization parameters:
            - select_related: List of fields for select_related
            - prefetch_related: List of fields for prefetch_related
            - prefetch_objects: Dict of field -> Prefetch objects
            - only_fields: List of fields to fetch (only())
            - defer_fields: List of fields to defer
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Apply optimizations if result is a QuerySet
            if isinstance(result, tuple) and len(result) == TUPLE_RESPONSE_LENGTH:
                status_code, data = result
                if isinstance(data, QuerySet):
                    data = _apply_optimizations(data, optimizations)
                    result = (status_code, data)
            elif isinstance(result, QuerySet):
                result = _apply_optimizations(result, optimizations)

            return result

        return wrapper

    return decorator


def _apply_optimizations(queryset: QuerySet, optimizations: dict) -> QuerySet:
    """Apply database optimizations to a QuerySet."""
    if select_related := optimizations.get("select_related"):
        queryset = queryset.select_related(*select_related)

    if prefetch_related := optimizations.get("prefetch_related"):
        queryset = queryset.prefetch_related(*prefetch_related)

    if prefetch_objects := optimizations.get("prefetch_objects"):
        for prefetch_obj in prefetch_objects.values():
            queryset = queryset.prefetch_related(prefetch_obj)

    if only_fields := optimizations.get("only_fields"):
        queryset = queryset.only(*only_fields)

    if defer_fields := optimizations.get("defer_fields"):
        queryset = queryset.defer(*defer_fields)

    return queryset


def cached_response(
    timeout: int = CACHE_TIMEOUT_MEDIUM,
    key_prefix: str = "api",
    vary_on_user: bool = False,
    vary_on_params: list[str] | None = None,
) -> Callable:
    """Cache decorator for API responses.

    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
        vary_on_user: Whether to include user in cache key
        vary_on_params: List of parameters to include in cache key
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            cache_key_parts = [key_prefix, func.__name__]

            if vary_on_user:
                request = None
                for arg in args:
                    if hasattr(arg, "user"):
                        request = arg
                        break
                    if hasattr(arg, "request"):
                        request = arg.request
                        break

                if request and request.user.is_authenticated:
                    cache_key_parts.append(f"user_{request.user.id}")
                else:
                    cache_key_parts.append("anonymous")

            if vary_on_params:
                cache_key_parts.extend(
                    [
                        f"{param}_{kwargs[param]}"
                        for param in vary_on_params
                        if param in kwargs
                    ]
                )

            cache_key = ":".join(str(part) for part in cache_key_parts)

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)

            return result

        return wrapper

    return decorator


def paginate_response(
    page_size: int = DEFAULT_PAGE_SIZE, max_page_size: int = MAX_PAGE_SIZE
) -> Callable:
    """Pagination decorator for list endpoints.

    Args:
        page_size: Default page size
        max_page_size: Maximum allowed page size
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Apply pagination if result is a successful QuerySet response
            if isinstance(result, tuple) and len(result) == TUPLE_RESPONSE_LENGTH:
                status_code, data = result

                if status_code == HTTP_OK and isinstance(data, QuerySet):
                    # Extract pagination params from request
                    request = None
                    for arg in args:
                        if hasattr(arg, "GET"):
                            request = arg
                            break
                        if hasattr(arg, "request"):
                            request = arg.request
                            break

                    if request:
                        page = int(request.GET.get("page", 1))
                        requested_page_size = int(
                            request.GET.get("page_size", page_size)
                        )
                        actual_page_size = min(requested_page_size, max_page_size)

                        paginated_data = paginate_queryset(data, page, actual_page_size)
                        return status_code, paginated_data

            return result

        return wrapper

    return decorator


def search_and_filter(**filter_config) -> Callable:
    """Search and filtering decorator.

    Args:
        **filter_config: Filter configuration:
            - search_fields: List of fields to search in
            - filter_fields: Dict of field -> filter type
            - ordering_fields: List of fields that can be ordered by
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Apply filters if result is a successful QuerySet response
            if isinstance(result, tuple) and len(result) == TUPLE_RESPONSE_LENGTH:
                status_code, data = result

                if status_code == HTTP_OK and isinstance(data, QuerySet):
                    # Extract request
                    request = None
                    for arg in args:
                        if hasattr(arg, "GET"):
                            request = arg
                            break
                        if hasattr(arg, "request"):
                            request = arg.request
                            break

                    if request:
                        data = _apply_search_and_filters(data, request, filter_config)
                        return status_code, data

            return result

        return wrapper

    return decorator


def _apply_search_and_filters(
    queryset: QuerySet, request: HttpRequest, config: dict
) -> QuerySet:
    """Apply search and filters to QuerySet."""
    # Apply search
    queryset = _apply_search(queryset, request, config)

    # Apply filters
    queryset = _apply_filters(queryset, request, config)

    # Apply ordering
    return _apply_ordering(queryset, request, config)


def _apply_search(queryset: QuerySet, request: HttpRequest, config: dict) -> QuerySet:
    """Apply search to QuerySet."""
    if search_fields := config.get("search_fields"):
        search_query = request.GET.get("search", "").strip()
        if search_query:
            q_objects = Q()
            for field in search_fields:
                q_objects |= Q(**{f"{field}__icontains": search_query})
            queryset = queryset.filter(q_objects)
    return queryset


def _apply_filters(queryset: QuerySet, request: HttpRequest, config: dict) -> QuerySet:
    """Apply filters to QuerySet."""
    if filter_fields := config.get("filter_fields"):
        for field, filter_type in filter_fields.items():
            param_value = request.GET.get(field)
            if param_value:
                if filter_type == "exact":
                    queryset = queryset.filter(**{field: param_value})
                elif filter_type == "icontains":
                    queryset = queryset.filter(**{f"{field}__icontains": param_value})
                elif filter_type == "boolean":
                    if param_value.lower() in ("true", "1", "yes"):
                        queryset = queryset.filter(**{field: True})
                    elif param_value.lower() in ("false", "0", "no"):
                        queryset = queryset.filter(**{field: False})
    return queryset


def _apply_ordering(queryset: QuerySet, request: HttpRequest, config: dict) -> QuerySet:
    """Apply ordering to QuerySet."""
    if ordering_fields := config.get("ordering_fields"):
        ordering = request.GET.get("ordering", "").strip()
        if ordering:
            valid_orderings = []
            for order_field_raw in ordering.split(","):
                order_field_clean = order_field_raw.strip()
                field_name = order_field_clean.lstrip("-")

                if field_name in ordering_fields:
                    valid_orderings.append(order_field_clean)

            if valid_orderings:
                queryset = queryset.order_by(*valid_orderings)
    return queryset


# Composed decorators for common patterns
def api_endpoint(
    require_auth: bool = True,
    require_admin: bool = False,
    cache_timeout: int | None = None,
    log_calls: bool = True,
    enable_pagination: bool = False,
    search_fields: list[str] | None = None,
    filter_fields: dict[str, str] | None = None,
    ordering_fields: list[str] | None = None,
    **optimization_params,
) -> Callable:
    """Composed decorator for common API endpoint patterns.

    Args:
        require_auth: Whether to require authentication
        require_admin: Whether to require admin permissions
        cache_timeout: Cache timeout (None = no caching)
        log_calls: Whether to log API calls
        enable_pagination: Whether to apply pagination
        search_fields: List of fields to search in
        filter_fields: Dict of field -> filter type
        ordering_fields: List of fields that can be ordered by
        **optimization_params: Database optimization parameters
    """

    def decorator(func: Callable) -> Callable:
        decorated_func = func

        # Apply decorators in reverse order (innermost first)
        if optimization_params:
            decorated_func = optimize_queryset(**optimization_params)(decorated_func)

        # Apply search and filtering
        if search_fields or filter_fields or ordering_fields:
            filter_config = {
                "search_fields": search_fields or [],
                "filter_fields": filter_fields or {},
                "ordering_fields": ordering_fields or [],
            }
            decorated_func = search_and_filter(**filter_config)(decorated_func)

        if enable_pagination:
            decorated_func = paginate_response()(decorated_func)

        if cache_timeout:
            decorated_func = cached_response(timeout=cache_timeout)(decorated_func)

        if require_admin:
            decorated_func = require_permissions(IsAdminUser)(decorated_func)
        elif require_auth:
            decorated_func = require_authentication(decorated_func)

        if log_calls:
            decorated_func = log_api_call()(decorated_func)

        # Always apply exception handling (outermost)
        return handle_exceptions(decorated_func)

    return decorator


# Specific decorators for different endpoint types
def list_endpoint(**kwargs) -> Callable:
    """Decorator for list endpoints with pagination and search."""
    defaults = {
        "require_auth": True,
        "enable_pagination": True,
        "log_calls": True,
        "cache_timeout": 300,
    }
    defaults.update(kwargs)
    return api_endpoint(**defaults)


def detail_endpoint(**kwargs) -> Callable:
    """Decorator for detail endpoints."""
    defaults = {
        "require_auth": True,
        "log_calls": True,
        "cache_timeout": 600,
    }
    defaults.update(kwargs)
    return api_endpoint(**defaults)


def create_endpoint(**kwargs) -> Callable:
    """Decorator for create endpoints."""
    defaults = {
        "require_auth": True,
        "log_calls": True,
    }
    defaults.update(kwargs)
    return api_endpoint(**defaults)


def update_endpoint(**kwargs) -> Callable:
    """Decorator for update endpoints."""
    defaults = {
        "require_auth": True,
        "log_calls": True,
    }
    defaults.update(kwargs)
    return api_endpoint(**defaults)


def delete_endpoint(**kwargs) -> Callable:
    """Decorator for delete endpoints."""
    defaults = {
        "require_auth": True,
        "log_calls": True,
    }
    defaults.update(kwargs)
    return api_endpoint(**defaults)


def admin_endpoint(**kwargs) -> Callable:
    """Decorator for admin-only endpoints."""
    defaults = {
        "require_admin": True,
        "log_calls": True,
    }
    defaults.update(kwargs)
    return api_endpoint(**defaults)
