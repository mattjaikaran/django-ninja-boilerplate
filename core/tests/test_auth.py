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

    def _post(self, client, path: str, payload: dict, **extra):
        return client.post(
            path, json.dumps(payload), content_type="application/json", **extra
        )

    def test_signup_answer_does_not_reveal_existing_accounts(
        self, api_client, user, mailoutbox
    ):
        taken_email = {
            "username": "newuser",
            "email": user.email,
            "password": "Str0ngP@ssword!",
        }
        taken_username = {
            "username": user.username,
            "email": "fresh1@example.com",
            "password": "Str0ngP@ssword!",
        }
        new = {
            "username": "brandnew",
            "email": "fresh2@example.com",
            "password": "Str0ngP@ssword!",
        }
        answers = [
            self._post(api_client, "/api/auth/signup", body)
            for body in (taken_email, taken_username, new)
        ]
        assert {(r.status_code, r.content) for r in answers} == {
            (answers[2].status_code, answers[2].content)
        }
        assert answers[2].status_code == 202
        # Only the new address got an account; each address got one email.
        assert User.objects.filter(email__iexact=user.email).count() == 1
        assert not User.objects.filter(email="fresh1@example.com").exists()
        assert User.objects.filter(email="fresh2@example.com").exists()
        assert sorted(m.to[0] for m in mailoutbox) == sorted(
            [user.email, "fresh1@example.com", "fresh2@example.com"]
        )

    def test_username_login_unknown_and_wrong_password_match(self, api_client, user):
        unknown = self._post(
            api_client,
            "/api/auth/login/username",
            {"username": "nobody-here", "password": "wrong-password"},
        )
        wrong = self._post(
            api_client,
            "/api/auth/login/username",
            {"username": user.username, "password": "wrong-password"},
        )
        assert (unknown.status_code, unknown.json()) == (
            wrong.status_code,
            wrong.json(),
        )

    @pytest.mark.parametrize(
        ("path", "field"),
        [("/api/auth/login", "email"), ("/api/token/pair", "email")],
    )
    def test_account_lockout_blocks_even_the_right_password(
        self, api_client, path, field
    ):
        user = UserFactory(set_password="Right-Passw0rd!")
        for _ in range(5):
            bad = self._post(
                api_client, path, {field: user.email, "password": "wrong-password"}
            )
            assert bad.status_code in (400, 401)
        good = self._post(
            api_client, path, {field: user.email, "password": "Right-Passw0rd!"}
        )
        assert good.status_code == 429

    def test_token_pair_and_login_share_the_account_counter(self, api_client):
        user = UserFactory(set_password="Right-Passw0rd!")
        for path in ["/api/token/pair"] * 3 + ["/api/auth/login"] * 2:
            self._post(api_client, path, {"email": user.email, "password": "nope"})
        response = self._post(
            api_client,
            "/api/auth/login",
            {"email": user.email, "password": "Right-Passw0rd!"},
        )
        assert response.status_code == 429

    def test_ip_lockout_spans_accounts(self, api_client, monkeypatch):
        # Stay under the 20/min anon-auth throttle so only the lockout answers.
        monkeypatch.setattr("core.security.brute_force.IP_MAX_ATTEMPTS", 3)
        user = UserFactory(set_password="Right-Passw0rd!")
        for i in range(3):
            self._post(
                api_client,
                "/api/token/pair",
                {"email": f"guess{i}@example.com", "password": "nope"},
            )
        same_ip = self._post(
            api_client,
            "/api/token/pair",
            {"email": user.email, "password": "Right-Passw0rd!"},
        )
        other_ip = self._post(
            api_client,
            "/api/token/pair",
            {"email": user.email, "password": "Right-Passw0rd!"},
            REMOTE_ADDR="203.0.113.9",
        )
        assert (same_ip.status_code, other_ip.status_code) == (429, 200)

    def test_admin_login_lockout_blocks_the_right_password(self, api_client):
        from django.urls import reverse

        admin_user = UserFactory(
            is_staff=True, is_superuser=True, set_password="Right-Passw0rd!"
        )
        url = reverse("admin:login")
        for _ in range(5):
            bad = api_client.post(url, {"username": admin_user.email, "password": "x"})
            assert bad.status_code == 200  # form re-rendered with an error
        good = api_client.post(
            url, {"username": admin_user.email, "password": "Right-Passw0rd!"}
        )
        assert good.status_code == 429

    def test_lockout_from_one_ip_does_not_lock_the_owner_elsewhere(self, api_client):
        """An attacker cannot lock an account for everyone (login DoS)."""
        user = UserFactory(set_password="Right-Passw0rd!")
        for _ in range(5):
            self._post(
                api_client,
                "/api/token/pair",
                {"email": user.email, "password": "nope"},
                REMOTE_ADDR="198.51.100.66",
            )
        owner = self._post(
            api_client,
            "/api/auth/login",
            {"email": user.email, "password": "Right-Passw0rd!"},
            REMOTE_ADDR="203.0.113.10",
        )
        assert owner.status_code == 200

    def test_username_and_email_login_share_one_counter(self, api_client):
        user = UserFactory(set_password="Right-Passw0rd!")
        for path, body in [
            ("/api/auth/login/username", {"username": user.username})
        ] * 3 + [("/api/auth/login", {"email": user.email})] * 2:
            self._post(api_client, path, {**body, "password": "nope"})
        response = self._post(
            api_client,
            "/api/auth/login/username",
            {"username": user.username, "password": "Right-Passw0rd!"},
        )
        assert response.status_code == 429

    def test_login_invalid_credentials_returns_400(self, api_client, user):
        payload = {"email": user.email, "password": "wrong-password"}
        response = api_client.post(
            "/api/auth/login",
            json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 400

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
        assert response.json()["id"] == str(user.id)
        assert not {"access", "refresh"} & response.json().keys()
        assert response.cookies["access_token"]["httponly"]
        assert response.cookies["refresh_token"]["httponly"]

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
