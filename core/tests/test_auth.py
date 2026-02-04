import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import OneTimePassword
from core.tests.factories import OneTimePasswordFactory, UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestAuthAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client

        return Client()

    @pytest.fixture
    def user(self):
        """Create a test user using factory."""
        return UserFactory()

    def test_passwordless_login_request(self, api_client, user):
        data = {"email": user.email}
        response = api_client.post(
            "/api/auth/passwordless/login/request",
            json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert "detail" in response.json()
        assert OneTimePassword.objects.filter(user=user).exists()

    def test_passwordless_login_verify(self, api_client, user):
        # Create OTP using factory
        otp = OneTimePasswordFactory(user=user, token="test-token")

        data = {"email": user.email, "token": "test-token"}
        response = api_client.post(
            "/api/auth/passwordless/login/verify",
            json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert "access" in response.json()
        assert "refresh" in response.json()

        # Check that OTP was marked as used
        otp.refresh_from_db()
        assert otp.is_used

    def test_passwordless_login_verify_invalid_token(self, api_client, user):
        data = {"email": user.email, "token": "invalid-token"}
        response = api_client.post(
            "/api/auth/passwordless/login/verify",
            json.dumps(data),
            content_type="application/json",
        )
        # 404 is returned when token doesn't exist
        assert response.status_code == 404

    def test_passwordless_login_verify_expired_token(self, api_client, user):
        # Create expired OTP
        expired_otp = OneTimePasswordFactory(
            user=user,
            token="expired-token",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        data = {"email": user.email, "token": "expired-token"}
        response = api_client.post(
            "/api/auth/passwordless/login/verify",
            json.dumps(data),
            content_type="application/json",
        )
        # 404 is returned when token is expired (not found in valid tokens)
        assert response.status_code == 404

    def test_passwordless_login_verify_used_token(self, api_client, user):
        # Create used OTP
        used_otp = OneTimePasswordFactory(user=user, token="used-token", is_used=True)

        data = {"email": user.email, "token": "used-token"}
        response = api_client.post(
            "/api/auth/passwordless/login/verify",
            json.dumps(data),
            content_type="application/json",
        )
        # 404 is returned when token is already used (not found in valid tokens)
        assert response.status_code == 404
