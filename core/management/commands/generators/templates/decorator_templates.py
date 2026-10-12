"""Decorator templates for code generation."""

# Rendered with str.format: {first_party_imports} is the app's isort block, so
# literal braces in the generated code are doubled. Staff and superuser checks
# use IsAdminUser and IsSuperUser from api.permissions instead.
RBAC_DECORATORS_TEMPLATE = '''"""RBAC decorators for controller routes.

Put them below the @http_* decorator of a route on a JWTAuth controller.
get_object(request, *args, **kwargs) returns the object for an object-level
check.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

{first_party_imports}

Check = Callable[[RBACService, Any, Any], bool]


def _require(check: Check, message: str, get_object: Callable | None) -> Callable:
    """Return a decorator that raises APIPermissionError when check fails."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise AuthenticationError
            content_object = (
                get_object(request, *args, **kwargs) if get_object else None
            )
            if not check(RBACService(), request.user, content_object):
                raise APIPermissionError(message)
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator


def require_permission(codename: str, get_object: Callable | None = None) -> Callable:
    """Require one permission."""
    return _require(
        lambda service, user, obj: service.user_has_permission(user, codename, obj),
        "Permission denied",
        get_object,
    )


def require_role(role_name: str, get_object: Callable | None = None) -> Callable:
    """Require one role."""
    return _require(
        lambda service, user, obj: service.user_has_role(user, role_name, obj),
        "Role required",
        get_object,
    )


def require_any_permission(
    *codenames: str, get_object: Callable | None = None
) -> Callable:
    """Require at least one of the permissions."""
    return _require(
        lambda service, user, obj: any(
            service.user_has_permission(user, codename, obj) for codename in codenames
        ),
        "Permission denied",
        get_object,
    )


def require_all_permissions(
    *codenames: str, get_object: Callable | None = None
) -> Callable:
    """Require every one of the permissions."""
    return _require(
        lambda service, user, obj: all(
            service.user_has_permission(user, codename, obj) for codename in codenames
        ),
        "Permission denied",
        get_object,
    )
'''

# Rendered with str.format: {first_party_imports} imports RBACService.
RBAC_MIDDLEWARE_TEMPLATE = '''"""RBAC middleware: permission helpers on request.user."""

from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin

{first_party_imports}


class RBACMiddleware(MiddlewareMixin):
    """Add has_permission, has_role and get_permissions to request.user.

    Middleware runs before the API authenticates a JWT bearer token, so the
    helpers exist only for session-authenticated requests.
    """

    def process_request(self, request: HttpRequest) -> None:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return
        service = RBACService()
        user.has_permission = lambda codename, obj=None: service.user_has_permission(
            user, codename, obj
        )
        user.has_role = lambda role_name, obj=None: service.user_has_role(
            user, role_name, obj
        )
        user.get_permissions = lambda obj=None: service.get_user_permissions(user, obj)
'''
