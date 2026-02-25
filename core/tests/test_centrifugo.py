"""Tests for Centrifugo integration (token generation + client)."""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from django.test import TestCase, override_settings

from api.centrifugo import (
    CentrifugoClient,
    generate_connection_token,
    generate_subscription_token,
)

CENTRIFUGO_SETTINGS = {
    "CENTRIFUGO_TOKEN_SECRET": "test-secret-key",
    "CENTRIFUGO_TOKEN_TTL": 3600,
    "CENTRIFUGO_URL": "http://centrifugo:8000",
    "CENTRIFUGO_API_KEY": "test-api-key",
}


@override_settings(**CENTRIFUGO_SETTINGS)
class TestConnectionToken(TestCase):
    """Test generate_connection_token."""

    def test_basic_token(self):
        token = generate_connection_token(user_id="user-123")
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])

        assert decoded["sub"] == "user-123"
        assert "iat" in decoded
        assert "exp" in decoded
        assert "info" not in decoded

    def test_token_with_info(self):
        info = {"username": "matt", "email": "matt@example.com"}
        token = generate_connection_token(user_id="user-123", info=info)
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])

        assert decoded["info"] == info

    def test_token_expiration_default(self):
        now = int(time.time())
        token = generate_connection_token(user_id="user-123")
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])

        # Should expire ~3600s from now (allow 5s tolerance)
        assert abs(decoded["exp"] - (now + 3600)) < 5

    def test_token_expiration_custom(self):
        expire_at = int(time.time()) + 7200
        token = generate_connection_token(user_id="user-123", expire_at=expire_at)
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])

        assert decoded["exp"] == expire_at

    def test_user_id_coerced_to_string(self):
        token = generate_connection_token(user_id=42)
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])

        assert decoded["sub"] == "42"


@override_settings(**CENTRIFUGO_SETTINGS)
class TestSubscriptionToken(TestCase):
    """Test generate_subscription_token."""

    def test_basic_token(self):
        token = generate_subscription_token(user_id="user-123", channel="chat:conv-abc")
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])

        assert decoded["sub"] == "user-123"
        assert decoded["channel"] == "chat:conv-abc"
        assert "iat" in decoded
        assert "exp" in decoded

    def test_token_with_info(self):
        info = {"role": "admin"}
        token = generate_subscription_token(
            user_id="user-123", channel="organization:org-1", info=info
        )
        decoded = jwt.decode(token, "test-secret-key", algorithms=["HS256"])

        assert decoded["info"] == info
        assert decoded["channel"] == "organization:org-1"


@override_settings(**CENTRIFUGO_SETTINGS)
class TestCentrifugoClient(TestCase):
    """Test CentrifugoClient HTTP wrapper."""

    def setUp(self):
        self.client = CentrifugoClient(
            url="http://centrifugo:8000",
            api_key="test-api-key",
        )

    @patch("api.centrifugo.httpx.post")
    def test_publish(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = self.client.publish("chat:123", {"text": "hello"})

        mock_post.assert_called_once_with(
            "http://centrifugo:8000/api",
            json={
                "method": "publish",
                "params": {"channel": "chat:123", "data": {"text": "hello"}},
            },
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "test-api-key",
            },
            timeout=5.0,
        )
        assert result == {"result": {}}

    @patch("api.centrifugo.httpx.post")
    def test_broadcast(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        channels = ["notifications:u1", "notifications:u2"]
        data = {"type": "alert", "message": "hi"}
        self.client.broadcast(channels, data)

        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["method"] == "broadcast"
        assert payload["params"]["channels"] == channels
        assert payload["params"]["data"] == data

    @patch("api.centrifugo.httpx.post")
    def test_subscribe(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        self.client.subscribe("user-1", "chat:conv-1")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["method"] == "subscribe"
        assert payload["params"] == {"user": "user-1", "channel": "chat:conv-1"}

    @patch("api.centrifugo.httpx.post")
    def test_unsubscribe(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        self.client.unsubscribe("user-1", "chat:conv-1")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["method"] == "unsubscribe"

    @patch("api.centrifugo.httpx.post")
    def test_disconnect(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        self.client.disconnect("user-1")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["method"] == "disconnect"
        assert payload["params"] == {"user": "user-1"}

    @patch("api.centrifugo.httpx.post")
    def test_presence(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"presence": {}}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = self.client.presence("chat:123")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["method"] == "presence"
        assert result == {"result": {"presence": {}}}

    @patch("api.centrifugo.httpx.post")
    def test_history(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"publications": []}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = self.client.history("chat:123", limit=10)

        payload = mock_post.call_args.kwargs["json"]
        assert payload["method"] == "history"
        assert payload["params"]["limit"] == 10

    @patch("api.centrifugo.httpx.post")
    def test_http_error_raises(self, mock_post):
        import httpx

        mock_post.side_effect = httpx.HTTPError("Connection refused")

        with pytest.raises(httpx.HTTPError):
            self.client.publish("chat:123", {"text": "hello"})
