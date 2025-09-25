"""Decorator templates for code generation."""

RBAC_DECORATORS_TEMPLATE = '''"""RBAC decorators for view protection."""

from functools import wraps
from typing import Callable, Optional, Any
from django.http import HttpRequest, HttpResponse
from django.core.exceptions import PermissionDenied
from ninja_extra.exceptions import APIException

from .services.rbac_service import RBACService


def require_permission(permission_codename: str, get_object: Optional[Callable] = None):
    """Decorator to require a specific permission for a view.

    Args:
        permission_codename: The permission codename to check
        get_object: Optional function to get the object for object-level permissions
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if not request.user.is_authenticated:
                raise APIException("Authentication required", 401)

            content_object = None
            if get_object:
                content_object = get_object(request, *args, **kwargs)

            if not RBACService.user_has_permission(
                request.user, permission_codename, content_object
            ):
                raise APIException("Permission denied", 403)

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(role_name: str, get_object: Optional[Callable] = None):
    """Decorator to require a specific role for a view.

    Args:
        role_name: The role name to check
        get_object: Optional function to get the object for object-level roles
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if not request.user.is_authenticated:
                raise APIException("Authentication required", 401)

            content_object = None
            if get_object:
                content_object = get_object(request, *args, **kwargs)

            if not RBACService.user_has_role(
                request.user, role_name, content_object
            ):
                raise APIException("Role required", 403)

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(*permission_codenames: str, get_object: Optional[Callable] = None):
    """Decorator to require any of the specified permissions.

    Args:
        permission_codenames: The permission codenames to check (user needs any one)
        get_object: Optional function to get the object for object-level permissions
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if not request.user.is_authenticated:
                raise APIException("Authentication required", 401)

            content_object = None
            if get_object:
                content_object = get_object(request, *args, **kwargs)

            has_permission = any(
                RBACService.user_has_permission(request.user, perm, content_object)
                for perm in permission_codenames
            )

            if not has_permission:
                raise APIException("Permission denied", 403)

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def require_all_permissions(*permission_codenames: str, get_object: Optional[Callable] = None):
    """Decorator to require all of the specified permissions.

    Args:
        permission_codenames: The permission codenames to check (user needs all)
        get_object: Optional function to get the object for object-level permissions
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if not request.user.is_authenticated:
                raise APIException("Authentication required", 401)

            content_object = None
            if get_object:
                content_object = get_object(request, *args, **kwargs)

            has_all_permissions = all(
                RBACService.user_has_permission(request.user, perm, content_object)
                for perm in permission_codenames
            )

            if not has_all_permissions:
                raise APIException("Permission denied", 403)

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def superuser_required(func: Callable) -> Callable:
    """Decorator to require superuser access."""
    @wraps(func)
    def wrapper(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            raise APIException("Authentication required", 401)

        if not request.user.is_superuser:
            raise APIException("Superuser access required", 403)

        return func(self, request, *args, **kwargs)
    return wrapper


def staff_required(func: Callable) -> Callable:
    """Decorator to require staff access."""
    @wraps(func)
    def wrapper(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            raise APIException("Authentication required", 401)

        if not request.user.is_staff:
            raise APIException("Staff access required", 403)

        return func(self, request, *args, **kwargs)
    return wrapper
'''

RBAC_MIDDLEWARE_TEMPLATE = '''"""RBAC middleware for automatic permission checking."""

from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .services.rbac_service import RBACService


class RBACMiddleware(MiddlewareMixin):
    \\"""Middleware to add RBAC helper methods to request object.\\"""

    def process_request(self, request: HttpRequest) -> None:
        \\"""Add RBAC methods to request object.\\"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Add convenience methods to request.user
            request.user.has_permission = lambda perm, obj=None: RBACService.user_has_permission(
                request.user, perm, obj
            )
            request.user.has_role = lambda role, obj=None: RBACService.user_has_role(
                request.user, role, obj
            )
            request.user.get_permissions = lambda obj=None: RBACService.get_user_permissions(
                request.user, obj
            )


class OrganizationMiddleware(MiddlewareMixin):
    \\"""Middleware to add organization context to requests.\\"""

    def process_request(self, request: HttpRequest) -> None:
        \\"""Add organization context to request.\\"""
        if hasattr(request, 'user') and request.user.is_authenticated:
            from .services.organization_service import OrganizationService

            # Add organization helper methods
            request.user.get_organizations = lambda: OrganizationService.get_user_organizations(
                request.user
            )

            # Add current organization if specified in headers
            org_id = request.headers.get('X-Organization-ID')
            if org_id:
                try:
                    from .models import Organization
                    org = Organization.objects.get(
                        id=org_id,
                        members__user=request.user,
                        members__status='active'
                    )
                    request.current_organization = org
                except Organization.DoesNotExist:
                    request.current_organization = None
            else:
                request.current_organization = None
'''
