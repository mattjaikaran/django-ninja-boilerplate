"""Realtime token endpoints require JWT and issue tokens only for own channels."""

import json

import jwt
import pytest
from django.test import Client
from ninja_jwt.tokens import AccessToken

from core.tests.factories import UserFactory

SECRET = "test-realtime-secret"


def _post(client, path, data, user=None):
    headers = {}
    if user is not None:
        client.cookies["access_token"] = str(AccessToken.for_user(user))
    return client.post(
        path, json.dumps(data), content_type="application/json", **headers
    )


@pytest.fixture(autouse=True)
def realtime_secret(settings):
    settings.CENTRIFUGO_TOKEN_SECRET = SECRET


@pytest.mark.django_db
class TestRealtimeTokens:
    def test_connection_token_carries_the_caller(self):
        user = UserFactory()
        response = _post(Client(), "/api/realtime/connection-token", {}, user)
        assert response.status_code == 200
        claims = jwt.decode(response.json()["token"], SECRET, algorithms=["HS256"])
        assert claims["sub"] == str(user.id)

    def test_own_notifications_channel_is_allowed(self):
        user = UserFactory()
        channel = f"notifications:{user.id}"
        response = _post(
            Client(), "/api/realtime/subscription-token", {"channel": channel}, user
        )
        assert response.status_code == 200
        claims = jwt.decode(response.json()["token"], SECRET, algorithms=["HS256"])
        assert claims == {**claims, "sub": str(user.id), "channel": channel}

    @pytest.mark.parametrize("channel", ["other", "chat:conversation-1", "notif"])
    def test_other_channels_are_forbidden(self, channel):
        user = UserFactory()
        other = UserFactory()
        target = f"notifications:{other.id}" if channel == "other" else channel
        response = _post(
            Client(), "/api/realtime/subscription-token", {"channel": target}, user
        )
        assert response.status_code == 403
