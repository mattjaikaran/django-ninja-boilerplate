"""Cookie transport for ninja-jwt tokens and CSRF enforcement on the API.

Browser clients keep the access and refresh tokens in httpOnly cookies and
send ``X-CSRFToken`` on every unsafe request. Non-browser clients keep using
``Authorization: Bearer`` (or ``X-API-Key``) with no auth cookie and skip
CSRF, because a browser never attaches those headers to a cross-site request
on its own.

The client contract lives in ``docs/COOKIE_AUTH.md``.
"""

import json
import logging
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.middleware.csrf import CsrfViewMiddleware
from ninja_jwt.settings import api_settings as jwt_settings
from ninja_jwt.tokens import RefreshToken

from api.exceptions import ErrorCode

logger = logging.getLogger(__name__)

API_PREFIX = "/api/"


def issue_token_pair(user: Any) -> tuple[str, str]:
    """Return a new ``(access, refresh)`` token pair for ``user``."""
    refresh = RefreshToken.for_user(user)  # type: ignore[misc]  # simplejwt stub types for_user as instance method
    return str(refresh.access_token), str(refresh)  # type: ignore[attr-defined]


def set_auth_cookies(response: HttpResponse, access: str, refresh: str) -> None:
    """Write the access and refresh tokens as httpOnly cookies."""
    common = {
        "secure": settings.AUTH_COOKIE_SECURE,
        "httponly": True,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
    }
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS_NAME,
        access,
        max_age=int(jwt_settings.ACCESS_TOKEN_LIFETIME.total_seconds()),
        path=settings.AUTH_COOKIE_ACCESS_PATH,
        **common,
    )
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH_NAME,
        refresh,
        max_age=int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
        path=settings.AUTH_COOKIE_REFRESH_PATH,
        **common,
    )


def clear_auth_cookies(response: HttpResponse) -> None:
    """Expire both auth cookies."""
    samesite = settings.AUTH_COOKIE_SAMESITE
    response.delete_cookie(
        settings.AUTH_COOKIE_ACCESS_NAME,
        path=settings.AUTH_COOKIE_ACCESS_PATH,
        samesite=samesite,
    )
    response.delete_cookie(
        settings.AUTH_COOKIE_REFRESH_NAME,
        path=settings.AUTH_COOKIE_REFRESH_PATH,
        samesite=samesite,
    )


def _csrf_protected_view(request: HttpRequest) -> HttpResponse:
    """Stand-in callback without ``csrf_exempt`` (Ninja exempts its views).

    ``CsrfViewMiddleware.process_view`` only reads the callback's
    ``csrf_exempt`` attribute; it never calls the callback.
    """
    raise NotImplementedError


def _has_header_credentials(request: HttpRequest) -> bool:
    return "HTTP_AUTHORIZATION" in request.META or "HTTP_X_API_KEY" in request.META


def _has_auth_cookie(request: HttpRequest) -> bool:
    cookies = request.COOKIES
    return (
        settings.AUTH_COOKIE_ACCESS_NAME in cookies
        or settings.AUTH_COOKIE_REFRESH_NAME in cookies
    )


def _is_csrf_exempt(path: str) -> bool:
    return path.startswith(tuple(settings.API_CSRF_EXEMPT_PATHS))


class ApiCsrfMiddleware(CsrfViewMiddleware):
    """Django's CSRF middleware, extended to cover the Ninja API.

    Replaces ``django.middleware.csrf.CsrfViewMiddleware``; non-API views keep
    Django's behaviour unchanged. For ``/api/`` requests:

    1. Unsafe methods must pass Django's CSRF check (cookie plus
       ``X-CSRFToken``), including login and refresh. Failure returns 403
       with code ``csrf_failed``. The only skips are paths in
       ``API_CSRF_EXEMPT_PATHS`` and requests that send ``Authorization`` or
       ``X-API-Key`` with no auth cookie. A request that carries an auth
       cookie is always checked, whatever headers it adds, because endpoints
       such as refresh and logout read the cookie directly.
    2. After the check, when no ``Authorization`` header is present, the
       access cookie is copied into it so the stock ``JWTAuth`` authenticates
       the request.

    The order matters: the header is set only after the CSRF decision, so a
    cookie can never skip CSRF by looking like a bearer header.
    """

    def process_view(
        self,
        request: HttpRequest,
        callback: Callable[..., Any],
        callback_args: tuple[Any, ...],
        callback_kwargs: dict[str, Any],
    ) -> HttpResponseForbidden | None:
        """Enforce CSRF on cookie-carrying API requests, then promote the cookie."""
        path = request.path_info
        header_only = _has_header_credentials(request) and not _has_auth_cookie(request)
        if not path.startswith(API_PREFIX) or header_only or _is_csrf_exempt(path):
            return super().process_view(
                request, callback, callback_args, callback_kwargs
            )

        rejection = super().process_view(
            request, _csrf_protected_view, callback_args, callback_kwargs
        )
        if rejection is not None:
            return rejection
        access = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
        if access and "HTTP_AUTHORIZATION" not in request.META:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {access}"
        return None

    def _reject(self, request: HttpRequest, reason: str) -> HttpResponseForbidden:
        if not request.path_info.startswith(API_PREFIX):
            # django-stubs omits the private CsrfViewMiddleware._reject hook.
            return super()._reject(request, reason)  # type: ignore[misc]
        logger.warning("Forbidden (%s): %s", reason, request.path)
        body = {
            "error": True,
            "message": "CSRF check failed. Fetch /api/auth/csrf and retry.",
            "code": ErrorCode.CSRF_FAILED.value,
        }
        return HttpResponseForbidden(json.dumps(body), content_type="application/json")
