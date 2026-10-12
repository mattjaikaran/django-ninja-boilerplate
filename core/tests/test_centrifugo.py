"""Tests for the Centrifugo connection token expiry."""

import time

import jwt
from django.test import TestCase, override_settings

from api.centrifugo import generate_connection_token

CENTRIFUGO_SETTINGS = {
    "CENTRIFUGO_TOKEN_SECRET": "test-secret-key",
    "CENTRIFUGO_TOKEN_TTL": 3600,
    "CENTRIFUGO_URL": "http://centrifugo:8000",
    "CENTRIFUGO_API_KEY": "test-api-key",
}


@override_settings(**CENTRIFUGO_SETTINGS)
class TestConnectionToken(TestCase):
    """Test generate_connection_token."""

    def test_token_expiration_default(self):
        now = int(time.time())
        token = generate_connection_token(user_id="user-123")
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])

        # Should expire ~3600s from now (allow 5s tolerance)
        assert abs(decoded["exp"] - (now + 3600)) < 5
