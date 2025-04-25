import pytest
import json
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from core.models import OneTimePassword

User = get_user_model()


@pytest.mark.django_db
class TestAuthAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client

        return Client()

    def test_passwordless_login_request(self, api_client, test_user):
        data = {"email": test_user.email}
        response = api_client.post(
            "/api/auth/passwordless/login/request",
            json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert "detail" in response.json()
        assert OneTimePassword.objects.filter(user=test_user).exists()

    def test_passwordless_login_verify(self, api_client, test_user):
        # Create OTP
        expires_at = datetime.now() + timedelta(minutes=15)
        otp = OneTimePassword.objects.create(
            user=test_user, token="test-token", expires_at=expires_at
        )

        data = {"email": test_user.email, "token": "test-token"}
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

    def test_passwordless_login_verify_invalid_token(self, api_client, test_user):
        data = {"email": test_user.email, "token": "invalid-token"}
        response = api_client.post(
            "/api/auth/passwordless/login/verify",
            json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == 403
        assert "detail" in response.json()
