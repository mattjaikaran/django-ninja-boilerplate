"""Cookie-only JWT authentication and browser CSRF enforcement."""

from django.conf import settings
from django.middleware.csrf import get_token, rotate_token
from ninja.security import APIKeyCookie
from ninja.utils import check_csrf
from ninja_jwt.authentication import JWTBaseAuthentication
from ninja_jwt.exceptions import InvalidToken, TokenError
from ninja_jwt.settings import api_settings
from ninja_jwt.tokens import RefreshToken


class CookieJWTAuth(JWTBaseAuthentication, APIKeyCookie):
    param_name = "access_token"

    def authenticate(self, request, key):
        if not key:
            return None
        return self.jwt_authenticate(request, key)


class RefreshCookieAuth(JWTBaseAuthentication, APIKeyCookie):
    param_name = "refresh_token"

    def authenticate(self, request, key):
        if not key:
            return None
        try:
            token = RefreshToken(key)
        except TokenError as exc:
            raise InvalidToken(str(exc)) from exc
        user = self.get_user(token)
        request.refresh_token = token
        request.user = user
        return user


class CookieCSRFMiddleware:
    """Check unsafe API requests independently of Ninja's exempt dispatch.

    Ninja exempts every dispatch from Django CSRF middleware. check_csrf uses
    a non-exempt callback and resets csrf_processing_done before checking.
    This also protects public login/refresh/logout and passwordless issuance.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        browser_auth = (
            request.path.startswith("/api/auth/") or "access_token" in request.COOKIES
        )
        if (
            browser_auth
            and request.path.startswith("/api/")
            and request.method not in ("GET", "HEAD", "OPTIONS", "TRACE")
        ):
            rejection = check_csrf(request)
            if rejection:
                return rejection
        return self.get_response(request)


def set_auth_cookies(response, refresh):
    secure = settings.AUTH_COOKIE_SECURE
    response.set_cookie(
        "access_token",
        str(refresh.access_token),
        max_age=int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()),
        path="/api/",
        secure=secure,
        httponly=True,
        samesite="Lax",
    )
    response.set_cookie(
        "refresh_token",
        str(refresh),
        max_age=int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
        path="/api/auth/",
        secure=secure,
        httponly=True,
        samesite="Lax",
    )


def issue_auth_cookies(request, response, user):
    rotate_token(request)
    get_token(request)
    set_auth_cookies(response, RefreshToken.for_user(user))


def delete_auth_cookies(response):
    response.delete_cookie("access_token", path="/api/", samesite="Lax")
    response.delete_cookie("refresh_token", path="/api/auth/", samesite="Lax")
