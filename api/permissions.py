"""Permission classes and decorators for the django-ninja-boilerplate API.

This module contains permission classes and decorators to handle
authorization and access control throughout the application.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib.auth.models import User
from django.http import HttpRequest
from ninja_extra.permissions import BasePermission

from .exceptions import APIPermissionError, AuthenticationError


class IsAuthenticated(BasePermission):
    """Permission class that requires user to be authenticated."""

    def has_permission(self, request: HttpRequest, view: Any) -> bool:  # noqa: ARG002
        return request.user and request.user.is_authenticated


class IsOwner(BasePermission):
    """Permission class that requires user to be the owner of the object."""

    def has_object_permission(self, request: HttpRequest, view: Any, obj: Any) -> bool:  # noqa: ARG002
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if object has a user or owner field
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "owner"):
            return obj.owner == request.user

        return False


class IsAdminUser(BasePermission):
    """Permission class that requires user to be an admin."""

    def has_permission(self, request: HttpRequest, view: Any) -> bool:  # noqa: ARG002
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsSuperUser(BasePermission):
    """Permission class that requires user to be a superuser."""

    def has_permission(self, request: HttpRequest, view: Any) -> bool:  # noqa: ARG002
        return (
            request.user and request.user.is_authenticated and request.user.is_superuser
        )


class IsOwnerOrAdmin(BasePermission):
    """Permission class that requires user to be owner or admin."""

    def has_object_permission(self, request: HttpRequest, view: Any, obj: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user is admin
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check if user is owner
        is_owner = IsOwner()
        return is_owner.has_object_permission(request, view, obj)


# Permission Decorators


def require_authentication(func: Callable) -> Callable:
    """Decorator that requires user to be authenticated."""

    @wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            msg = "Authentication required"
            raise AuthenticationError(msg)
        return func(request, *args, **kwargs)

    return wrapper


def require_admin(func: Callable) -> Callable:
    """Decorator that requires user to be an admin."""

    @wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            msg = "Authentication required"
            raise AuthenticationError(msg)

        if not request.user.is_staff:
            msg = "Admin access required"
            raise APIPermissionError(msg)

        return func(request, *args, **kwargs)

    return wrapper


def require_superuser(func: Callable) -> Callable:
    """Decorator that requires user to be a superuser."""

    @wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user or not request.user.is_authenticated:
            msg = "Authentication required"
            raise AuthenticationError(msg)

        if not request.user.is_superuser:
            msg = "Superuser access required"
            raise APIPermissionError(msg)

        return func(request, *args, **kwargs)

    return wrapper


def require_permission(permission: str) -> Callable:
    """Decorator that requires a specific permission."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                msg = "Authentication required"
                raise AuthenticationError(msg)

            if not request.user.has_perm(permission):
                msg = f"Permission required: {permission}"
                raise APIPermissionError(msg)

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_owner(obj_param: str = "obj") -> Callable:
    """Decorator that requires user to be the owner of an object."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                msg = "Authentication required"
                raise AuthenticationError(msg)

            # Get the object from kwargs
            obj = kwargs.get(obj_param)
            if not obj:
                msg = "Object not found"
                raise APIPermissionError(msg)

            # Check ownership
            is_owner = False
            if hasattr(obj, "user"):
                is_owner = obj.user == request.user
            elif hasattr(obj, "owner"):
                is_owner = obj.owner == request.user

            if not is_owner and not request.user.is_staff:
                msg = "Access denied: You are not the owner"
                raise APIPermissionError(msg)

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_owner_or_admin(obj_param: str = "obj") -> Callable:
    """Decorator that requires user to be owner or admin."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                msg = "Authentication required"
                raise AuthenticationError(msg)

            # Admin users can access everything
            if request.user.is_staff or request.user.is_superuser:
                return func(request, *args, **kwargs)

            # Get the object from kwargs
            obj = kwargs.get(obj_param)
            if not obj:
                msg = "Object not found"
                raise APIPermissionError(msg)

            # Check ownership
            is_owner = False
            if hasattr(obj, "user"):
                is_owner = obj.user == request.user
            elif hasattr(obj, "owner"):
                is_owner = obj.owner == request.user

            if not is_owner:
                msg = "Access denied: You are not the owner"
                raise APIPermissionError(msg)

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def check_rate_limit(
    limit: int, window: int = 3600, key_func: Callable | None = None
) -> Callable:
    """Decorator to implement rate limiting."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            from django.core.cache import cache  # noqa: PLC0415

            from .utils import get_client_ip  # noqa: PLC0415

            # Generate cache key
            if key_func:
                key = key_func(request, *args, **kwargs)
            else:
                ip = get_client_ip(request)
                key = f"rate_limit:{ip}:{func.__name__}"

            # Check current count
            current = cache.get(key, 0)
            if current >= limit:
                from .exceptions import RateLimitError  # noqa: PLC0415

                msg = f"Rate limit exceeded: {limit} requests per {window} seconds"
                raise RateLimitError(msg)

            # Increment count
            cache.set(key, current + 1, window)

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


# Helper Functions


def get_user_permissions(user: User) -> list:
    """Get all permissions for a user."""
    if not user or not user.is_authenticated:
        return []

    permissions = []

    # Add user permissions
    permissions.extend(user.user_permissions.values_list("codename", flat=True))

    # Add group permissions
    for group in user.groups.all():
        permissions.extend(group.permissions.values_list("codename", flat=True))

    return list(set(permissions))


def has_any_permission(user: User, permissions: list) -> bool:
    """Check if user has any of the specified permissions."""
    if not user or not user.is_authenticated:
        return False

    user_permissions = get_user_permissions(user)
    return any(perm in user_permissions for perm in permissions)


def has_all_permissions(user: User, permissions: list) -> bool:
    """Check if user has all of the specified permissions."""
    if not user or not user.is_authenticated:
        return False

    user_permissions = get_user_permissions(user)
    return all(perm in user_permissions for perm in permissions)


def can_access_admin(user: User) -> bool:
    """Check if user can access admin interface."""
    return user and user.is_authenticated and user.is_staff


def can_modify_object(user: User, obj: Any) -> bool:
    """Check if user can modify an object."""
    if not user or not user.is_authenticated:
        return False

    # Admins can modify everything
    if user.is_staff or user.is_superuser:
        return True

    # Check ownership
    if hasattr(obj, "user"):
        return obj.user == user
    if hasattr(obj, "owner"):
        return obj.owner == user

    return False
