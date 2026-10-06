"""Refresh-token rotation with reuse detection, and bulk revocation.

Every refresh goes through ``rotate_refresh_token``: ``/api/auth/refresh``
(cookie and bearer) and ``/api/token/refresh`` (via ``NINJA_JWT``
``TOKEN_OBTAIN_PAIR_REFRESH_INPUT_SCHEMA``). Rotation blacklists the presented
token and records the new one as outstanding, so the blacklist knows every
refresh token the API issued.

A blacklisted refresh token that comes back long after its rotation means a
copy of it leaked, or the client lost the rotated token. Either way the API
cannot tell the real client from the attacker, so it revokes every
outstanding refresh token of the user and returns 401.

Inside ``REUSE_GRACE_SECONDS`` of the rotation, a repeat is a benign race:
two tabs sharing one cookie jar, a React StrictMode double effect, or a
retried fetch. That repeat gets 401 without revocation; the browser already
holds the successor cookie from the first response. Access tokens stay valid
until they expire (``ACCESS_TOKEN_LIFETIME``). ``docs/COOKIE_AUTH.md``
describes the contract.
"""

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from ninja import Schema
from ninja_jwt.exceptions import InvalidToken, TokenBackendError
from ninja_jwt.schema import InputSchemaMixin, SchemaInputService
from ninja_jwt.settings import api_settings as jwt_settings
from ninja_jwt.state import token_backend
from ninja_jwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from ninja_jwt.tokens import RefreshToken
from ninja_jwt.utils import datetime_from_epoch
from pydantic import model_validator

logger = logging.getLogger(__name__)

# A replay this soon after the rotation is a concurrent refresh, not theft.
REUSE_GRACE_SECONDS = 30


def revoke_user_refresh_tokens(user_id: Any) -> int:
    """Blacklist every unexpired refresh token of ``user_id``.

    Returns the number of tokens revoked. Call it when a password changes,
    a password is reset, or a refresh token is reused.
    """
    pending = list(
        OutstandingToken.objects.filter(
            user_id=user_id,
            expires_at__gt=timezone.now(),
            blacklistedtoken__isnull=True,
        )
    )
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in pending],
        ignore_conflicts=True,
    )
    return len(pending)


def _decode_refresh(raw_refresh: str) -> dict[str, Any]:
    """Return the payload of a validly signed, unexpired refresh token.

    Does not check the blacklist. Raises ``InvalidToken`` (401) otherwise.
    """
    try:
        payload = token_backend.decode(raw_refresh, verify=True)
    except TokenBackendError as exc:
        raise InvalidToken("Token is invalid or expired") from exc
    if payload.get(jwt_settings.TOKEN_TYPE_CLAIM) != RefreshToken.token_type:
        raise InvalidToken("Token has wrong type")
    if not payload.get(jwt_settings.JTI_CLAIM) or not payload.get(
        jwt_settings.USER_ID_CLAIM
    ):
        raise InvalidToken("Token is invalid or expired")
    return payload


def rotate_refresh_token(raw_refresh: str) -> tuple[str, str]:
    """Rotate ``raw_refresh`` and return the new ``(access, refresh)`` pair.

    Raises ``InvalidToken`` (401) for an invalid, expired, or blacklisted
    token. A blacklisted token also revokes all refresh tokens of its user.
    """
    payload = _decode_refresh(raw_refresh)
    jti = payload[jwt_settings.JTI_CLAIM]
    user_id = payload[jwt_settings.USER_ID_CLAIM]
    user = (
        get_user_model().objects.filter(**{jwt_settings.USER_ID_FIELD: user_id}).first()
    )
    # A deactivated account must not keep minting access tokens.
    if user is None or not user.is_active:
        raise InvalidToken("Token is invalid or expired")

    with transaction.atomic():
        # Tokens rotated before this module existed have no outstanding row.
        outstanding, _ = OutstandingToken.objects.get_or_create(
            jti=jti,
            defaults={
                "user": user,
                "token": raw_refresh,
                "expires_at": datetime_from_epoch(payload["exp"]),
            },
        )
        # The row lock serialises concurrent rotations of the same token, so
        # the second one sees the blacklist entry the first one wrote.
        outstanding = OutstandingToken.objects.select_for_update().get(
            pk=outstanding.pk
        )
        blacklisted = BlacklistedToken.objects.filter(token=outstanding).first()
        reused = blacklisted is not None
        if not reused:
            refresh = RefreshToken(raw_refresh)
            access = str(refresh.access_token)
            BlacklistedToken.objects.create(token=outstanding)
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            new_refresh = str(refresh)
            OutstandingToken.objects.create(
                user=user,
                jti=refresh[jwt_settings.JTI_CLAIM],
                token=new_refresh,
                created_at=refresh.current_time,
                expires_at=datetime_from_epoch(refresh["exp"]),
            )

    if blacklisted is not None:
        age = (timezone.now() - blacklisted.blacklisted_at).total_seconds()
        if age <= REUSE_GRACE_SECONDS:
            logger.info("Concurrent refresh for user id %s; no revocation", user.pk)
            raise InvalidToken("Token is blacklisted")
        revoked = revoke_user_refresh_tokens(user.pk)
        logger.warning(
            "Refresh token reuse for user id %s; revoked %d refresh tokens",
            user.pk,
            revoked,
        )
        raise InvalidToken("Token is blacklisted")
    return access, new_refresh


class TokenRefreshInputSchema(Schema, InputSchemaMixin):
    """``/api/token/refresh`` request body."""

    refresh: str

    @classmethod
    def get_response_schema(cls) -> type[Schema]:
        return TokenRefreshOutputSchema


class TokenRefreshOutputSchema(Schema):
    """``/api/token/refresh`` response: the rotated pair."""

    refresh: str
    access: str | None

    @model_validator(mode="before")
    @classmethod
    def rotate(cls, values: Any) -> Any:
        data = SchemaInputService(values, cls.model_config).get_values()
        if isinstance(data, dict) and "access" not in data:
            if not data.get("refresh"):
                raise InvalidToken("Token is invalid or expired")
            access, refresh = rotate_refresh_token(data["refresh"])
            return {"access": access, "refresh": refresh}
        return values
