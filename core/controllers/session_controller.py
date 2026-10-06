"""Browser session endpoints for the httpOnly cookie contract.

CSRF bootstrap, cookie refresh with rotation, and logout. The client contract
is in ``docs/COOKIE_AUTH.md``. Every unsafe method needs ``X-CSRFToken``
(``core.security.cookie_auth.ApiCsrfMiddleware``).
"""

import logging
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from ninja_extra import api_controller, http_get, http_post
from ninja_extra.exceptions import APIException
from ninja_extra.throttling import DynamicRateThrottle, throttle
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.exceptions import TokenError
from ninja_jwt.settings import api_settings as jwt_settings
from ninja_jwt.tokens import RefreshToken

from api.decorators import log_api_call
from core.schemas import (
    CsrfTokenSchema,
    MessageResponse,
    RefreshTokenSchema,
    TokenRefreshResponse,
)
from core.security.cookie_auth import clear_auth_cookies, set_auth_cookies
from core.security.refresh_tokens import rotate_refresh_token

logger = logging.getLogger(__name__)


@api_controller("/auth", tags=["Auth"], auth=JWTAuth())
class SessionController:
    """CSRF, refresh, and logout for cookie and bearer clients.

    Public endpoints (no JWT required):
        GET  /auth/csrf     — set the csrftoken cookie
        POST /auth/refresh  — rotate the refresh token
        POST /auth/logout   — blacklist the refresh token, clear cookies
    """

    @http_get("/csrf", response={200: CsrfTokenSchema}, auth=None)
    def get_csrf_token(self, request):
        """Set the readable ``csrftoken`` cookie and return the same token.

        Call once before login; echo the cookie in ``X-CSRFToken`` on every
        POST, PUT, PATCH, and DELETE.
        """
        return 200, CsrfTokenSchema(csrf_token=get_token(request))

    @http_post(
        "/refresh",
        response={200: TokenRefreshResponse, 400: dict, 401: dict},
        auth=None,
    )
    @throttle(DynamicRateThrottle, scope="anon-auth")
    def refresh(self, request, response: HttpResponse, payload: RefreshTokenSchema):
        """Rotate the refresh token and issue a new access token.

        Browser clients send an empty body; the refresh token comes from the
        httpOnly cookie and the new pair goes back as cookies only, so page
        scripts never see a token. Bearer clients send ``refresh`` in the body
        and get the new pair in the body. The old refresh token is blacklisted
        either way. Presenting a blacklisted refresh token again revokes every
        refresh token of its user (``core.security.refresh_tokens``).

        Returns:
            Tuple of (200, TokenRefreshResponse), (400, error_dict) when no
            refresh token is present, or 401 for an invalid, expired, or
            blacklisted token.
        """
        if payload.refresh:
            access, refresh = rotate_refresh_token(payload.refresh)
            return 200, TokenRefreshResponse(access=access, refresh=refresh)

        cookie_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
        if not cookie_refresh:
            return 400, {"error": "No refresh token in the body or cookie"}
        access, refresh = rotate_refresh_token(cookie_refresh)
        set_auth_cookies(response, access, refresh)
        return 200, TokenRefreshResponse()

    @http_post("/logout", response={200: MessageResponse, 400: dict}, auth=None)
    @log_api_call()
    def logout(self, request, response: HttpResponse, payload: RefreshTokenSchema):
        """Blacklist the refresh token and clear both auth cookies.

        The refresh token comes from the body (bearer clients) or the httpOnly
        cookie (browser clients); holding it is the credential. No access
        token is needed: the access cookie expires after an hour, and logout
        must still revoke the 7-day refresh token. When a valid access token
        is present, the refresh token must belong to the same user. The
        access token itself stays valid until its own expiry. CSRF still
        applies whenever an auth cookie is present.

        Logout is idempotent: a missing, invalid, expired, or
        already-blacklisted refresh token still returns success because that
        token is already unusable.

        Returns:
            Tuple of (200, MessageResponse) confirming the logout, or
            (400, error_dict) when the refresh token belongs to another user.
        """
        raw_refresh = payload.refresh or request.COOKIES.get(
            settings.AUTH_COOKIE_REFRESH_NAME
        )
        if raw_refresh:
            try:
                token = RefreshToken(raw_refresh)
                caller = _access_token_user(request)
                owner_id = str(token[jwt_settings.USER_ID_CLAIM])
                if caller is not None and owner_id != str(caller.pk):
                    return 400, {"error": "Refresh token belongs to another user"}
                token.blacklist()
            except TokenError:
                # Idempotent logout: an unusable refresh token is already revoked.
                logger.info("Logout received an unusable refresh token; ignoring")
        clear_auth_cookies(response)
        return 200, {"message": "Successfully logged out", "success": True}


def _access_token_user(request: HttpRequest) -> Any:
    """Return the user of a valid access token on ``request``, else None."""
    try:
        return JWTAuth()(request)
    except APIException:
        return None
