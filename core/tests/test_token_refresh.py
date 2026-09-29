"""Behavioral tests for JWT refresh rotation, logout revocation, and pruning.

Covers the v1.12 refresh-rotation contract:

- Refresh tokens rotate: each refresh returns a new refresh token.
- Rotated (old) refresh tokens are blacklisted and rejected.
- Logout blacklists the supplied refresh token; the access token stays valid
  until its own expiry.
- Expired outstanding tokens are pruned by the scheduled task.
"""

import json
import subprocess
import sys
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken

from core.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def tokens_for(user) -> dict:
    """Issue an access/refresh pair for *user* (what a real login returns)."""
    refresh = RefreshToken.for_user(user)
    return {"token": str(refresh.access_token), "refresh": str(refresh)}


def refresh(client: Client, refresh_token: str):
    """POST /api/token/refresh with the given refresh token."""
    return client.post(
        "/api/token/refresh",
        json.dumps({"refresh": refresh_token}),
        content_type="application/json",
    )


def logout(client: Client, access: str, refresh_token: str):
    """POST /api/auth/logout with the refresh token and access auth."""
    return client.post(
        "/api/auth/logout",
        json.dumps({"refresh": refresh_token}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )


class TestLoginRefreshFlow:
    @pytest.mark.parametrize(
        ("path", "field"),
        [("/api/auth/login", "email"), ("/api/auth/login/username", "username")],
    )
    def test_login_tokens_rotate_and_logout(self, client, path, field):
        user = UserFactory(set_password="testpass123")
        response = client.post(
            path,
            json.dumps({field: getattr(user, field), "password": "testpass123"}),
            content_type="application/json",
        )
        assert response.status_code == 200, response.content
        tokens = response.json()
        rotated = refresh(client, tokens["refresh"])
        assert rotated.status_code == 200
        assert refresh(client, tokens["refresh"]).status_code == 401
        assert (
            logout(client, tokens["token"], rotated.json()["refresh"]).status_code
            == 200
        )
        assert refresh(client, rotated.json()["refresh"]).status_code == 401


class TestRefreshRotation:
    def test_refresh_rotates_and_blacklists_old_token(self, client):
        user = UserFactory()
        old_refresh = tokens_for(user)["refresh"]

        response = refresh(client, old_refresh)
        assert response.status_code == 200, response.content
        payload = response.json()
        assert payload["refresh"] != old_refresh

        # The rotated (old) refresh token is now blacklisted.
        assert refresh(client, old_refresh).status_code == 401

        # The newly issued refresh token still works.
        assert refresh(client, payload["refresh"]).status_code == 200


class TestLogoutRevocation:
    def test_logout_blacklists_refresh_token(self, client):
        user = UserFactory()
        tokens = tokens_for(user)
        access, token = tokens["token"], tokens["refresh"]

        assert logout(client, access, token).status_code == 200

        # The blacklisted refresh token can no longer mint access tokens.
        assert refresh(client, token).status_code == 401

    def test_access_token_remains_valid_after_logout(self, client):
        user = UserFactory()
        tokens = tokens_for(user)
        access, token = tokens["token"], tokens["refresh"]

        assert logout(client, access, token).status_code == 200

        response = client.get("/api/auth/me", HTTP_AUTHORIZATION=f"Bearer {access}")
        assert response.status_code == 200

    def test_logout_is_idempotent(self, client):
        user = UserFactory()
        tokens = tokens_for(user)
        access, token = tokens["token"], tokens["refresh"]

        assert logout(client, access, token).status_code == 200
        # A second logout with the already-blacklisted token still succeeds.
        assert logout(client, access, token).status_code == 200

    def test_logout_cannot_revoke_another_users_refresh_token(self, client):
        actor = UserFactory()
        owner = UserFactory()
        actor_access = tokens_for(actor)["token"]
        owner_refresh = tokens_for(owner)["refresh"]

        response = logout(client, actor_access, owner_refresh)
        assert response.status_code == 400
        assert refresh(client, owner_refresh).status_code == 200

    def test_logout_requires_refresh_token_in_body(self, client):
        user = UserFactory()
        access = tokens_for(user)["token"]

        response = client.post(
            "/api/auth/logout",
            json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        assert response.status_code == 422


class TestTokenPruning:
    def test_flush_expired_tokens_deletes_only_expired(self):
        from ninja_jwt.token_blacklist.models import BlacklistedToken, OutstandingToken

        from core.tasks import flush_expired_tokens

        expired = OutstandingToken.objects.create(
            jti="expired-jti",
            token="expired-token",
            expires_at=timezone.now() - timedelta(days=1),
        )
        BlacklistedToken.objects.create(token=expired)
        OutstandingToken.objects.create(
            jti="live-jti",
            token="live-token",
            expires_at=timezone.now() + timedelta(days=1),
        )

        result = flush_expired_tokens()

        assert result["deleted"] == 1
        assert not BlacklistedToken.objects.filter(token=expired).exists()
        assert not OutstandingToken.objects.filter(jti="expired-jti").exists()
        assert OutstandingToken.objects.filter(jti="live-jti").exists()

    def test_flush_task_is_backend_neutral_handle(self):
        from api.tasks.contract import TaskHandle
        from core.tasks import flush_expired_tokens

        # The task must be registered through the backend-neutral facade, so it
        # runs on whichever TASK_BACKEND is configured (celery, huey, django_q,
        # django_rq, dramatiq), not just Celery.
        assert isinstance(flush_expired_tokens, TaskHandle)
        assert flush_expired_tokens.name == "core.flush_expired_tokens"

    def test_flush_expired_tokens_is_scheduled_in_celery_beat(self):
        from celery.schedules import crontab

        from api.celery import app

        entry = app.conf.beat_schedule["flush-expired-jwt-tokens-daily"]
        assert entry["task"] == "core.flush_expired_tokens"
        schedule = entry["schedule"]
        assert isinstance(schedule, crontab)
        assert schedule.minute == {0}
        assert schedule.hour == {3}

    def test_flush_expired_tokens_management_command(self):
        from django.core.management import call_command
        from ninja_jwt.token_blacklist.models import OutstandingToken

        OutstandingToken.objects.create(
            jti="expired-jti",
            token="expired-token",
            expires_at=timezone.now() - timedelta(days=1),
        )

        # Portable entry point invokable by cron/systemd/Kubernetes regardless
        # of the configured task backend.
        call_command("flush_expired_tokens", verbosity=0)

        assert not OutstandingToken.objects.filter(jti="expired-jti").exists()


class TestSigningKeySeparation:
    def test_jwt_signing_key_uses_dedicated_setting(self, settings):
        # NINJA_JWT must sign with the dedicated NINJA_JWT_SIGNING_KEY, not
        # SECRET_KEY, so production can require them to differ.
        assert hasattr(settings, "NINJA_JWT_SIGNING_KEY")
        assert settings.NINJA_JWT["SIGNING_KEY"] == settings.NINJA_JWT_SIGNING_KEY


def test_flush_task_registers_under_alternate_backend():
    """The flush task must register through the backend-neutral facade on a
    non-Celery backend, proving ``core.tasks`` has no Celery-only assumptions.

    Runs in a subprocess because Django caches settings per process and the
    task decorator is resolved once at import time against ``TASK_BACKEND``.
    """
    script = """
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
os.environ['TASK_BACKEND'] = 'huey'
os.environ['REDIS_URL'] = 'redis://127.0.0.1:6380/0'
import django
django.setup()
from api.tasks.contract import TaskHandle
from core.tasks import flush_expired_tokens
assert isinstance(flush_expired_tokens, TaskHandle), type(flush_expired_tokens)
assert flush_expired_tokens.name == 'core.flush_expired_tokens'
assert callable(flush_expired_tokens.func)
print('OK')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
