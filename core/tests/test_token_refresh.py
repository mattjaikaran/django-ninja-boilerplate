"""Cookie refresh rotation, CSRF, logout revocation, and pruning behavior."""

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


def csrf_headers(client):
    return {"HTTP_X_CSRFTOKEN": client.get("/api/auth/csrf").json()["csrfToken"]}


def refresh(client, token=None):
    if token is not None:
        client.cookies["refresh_token"] = token
    return client.post("/api/auth/refresh", **csrf_headers(client))


@pytest.mark.django_db
class TestCookieAuthentication:
    @pytest.mark.parametrize(
        ("path", "field"),
        [("/api/auth/login", "email"), ("/api/auth/login/username", "username")],
    )
    def test_login_rotation_logout(self, path, field):
        client = Client(enforce_csrf_checks=True)
        user = UserFactory(set_password="testpass123")
        response = client.post(
            path,
            json.dumps({field: getattr(user, field), "password": "testpass123"}),
            content_type="application/json",
            **csrf_headers(client),
        )
        assert response.status_code == 200, response.content
        assert response.json()["id"] == str(user.id)
        assert not {"token", "access", "refresh"} & response.json().keys()
        assert response.cookies["access_token"]["httponly"]
        assert response.cookies["access_token"]["path"] == "/api/"
        assert response.cookies["refresh_token"]["path"] == "/api/auth/"
        assert response.cookies["refresh_token"]["samesite"] == "Lax"
        assert client.get("/api/auth/me").status_code == 200
        old = client.cookies["refresh_token"].value
        rotated = refresh(client)
        assert rotated.status_code == 200
        new = client.cookies["refresh_token"].value
        assert new != old
        assert refresh(client, old).status_code == 401
        client.cookies["refresh_token"] = new
        logout = client.post("/api/auth/logout", **csrf_headers(client))
        assert logout.status_code == 200
        assert logout.cookies["access_token"]["max-age"] == 0
        assert logout.cookies["refresh_token"]["max-age"] == 0
        assert refresh(client, new).status_code == 401

    @pytest.mark.parametrize(
        "path", ["/api/auth/login", "/api/auth/refresh", "/api/auth/logout"]
    )
    def test_public_unsafe_auth_requires_csrf(self, path):
        client = Client(enforce_csrf_checks=True)
        assert (
            client.post(path, "{}", content_type="application/json").status_code == 403
        )

    def test_authenticated_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.cookies["access_token"] = str(
            RefreshToken.for_user(UserFactory()).access_token
        )
        assert (
            client.post(
                "/api/todos/", '{"title":"test"}', content_type="application/json"
            ).status_code
            == 403
        )

    def test_bearer_header_is_not_application_authentication(self):
        token = RefreshToken.for_user(UserFactory()).access_token
        assert (
            Client()
            .get("/api/auth/me", HTTP_AUTHORIZATION=f"Bearer {token}")
            .status_code
            == 401
        )

    def test_logout_without_access_cookie_is_idempotent(self):
        client = Client(enforce_csrf_checks=True)
        token = str(RefreshToken.for_user(UserFactory()))
        client.cookies["refresh_token"] = token
        assert (
            client.post("/api/auth/logout", **csrf_headers(client)).status_code == 200
        )
        assert (
            client.post("/api/auth/logout", **csrf_headers(client)).status_code == 200
        )
        assert refresh(client, token).status_code == 401

    @pytest.mark.parametrize("token", ["invalid", ""])
    def test_malformed_refresh_is_unauthorized(self, token):
        client = Client(enforce_csrf_checks=True)
        assert refresh(client, token).status_code == 401

    def test_production_cookies_are_secure(self, settings):
        from django.http import HttpResponse
        from core.security.cookie_auth import set_auth_cookies

        settings.AUTH_COOKIE_SECURE = True
        response = HttpResponse()
        set_auth_cookies(response, RefreshToken.for_user(UserFactory()))
        assert response.cookies["access_token"]["secure"]
        assert response.cookies["refresh_token"]["secure"]


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
