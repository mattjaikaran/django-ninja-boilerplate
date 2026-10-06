"""Behavioral tests for JWT refresh rotation, logout revocation, and pruning.

Covers the refresh-rotation contract:

- Refresh tokens rotate: each refresh returns a new refresh token.
- Rotated (old) refresh tokens are blacklisted and rejected.
- A rotated token presented again after the grace window revokes every
  refresh token of the user; inside the window (concurrent tabs) it only
  gets 401.
- A password change revokes every refresh token of the user.
- Logout blacklists the supplied refresh token; the access token stays valid
  until its own expiry.
- Expired outstanding tokens are pruned by the scheduled task.
"""

import json
import subprocess
import sys
import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.test import Client
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken

from core.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def csrf_headers(client):
    return {"HTTP_X_CSRFTOKEN": client.get("/api/auth/csrf").json()["csrfToken"]}


def _age_blacklist_past_grace() -> None:
    """Move every blacklist entry outside the concurrent-refresh grace window."""
    from ninja_jwt.token_blacklist.models import BlacklistedToken

    from core.security.refresh_tokens import REUSE_GRACE_SECONDS

    BlacklistedToken.objects.update(
        blacklisted_at=timezone.now() - timedelta(seconds=REUSE_GRACE_SECONDS + 1)
    )


def refresh(client: Client, refresh_token: str):
    """POST /api/token/refresh with the given refresh token."""
    return client.post(
        "/api/token/refresh",
        json.dumps({"refresh": refresh_token}),
        content_type="application/json",
    )


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

class TestRefreshRotation:
    def test_refresh_rotates_and_new_token_keeps_working(self, client):
        user = UserFactory()
        old_refresh = tokens_for(user)["refresh"]

        response = refresh(client, old_refresh)
        assert response.status_code == 200, response.content
        new_refresh = response.json()["refresh"]
        assert new_refresh != old_refresh
        assert refresh(client, new_refresh).status_code == 200

    @pytest.mark.parametrize("path", ["/api/token/refresh", "/api/auth/refresh"])
    def test_reused_refresh_token_revokes_all_user_refresh_tokens(self, client, path):
        user = UserFactory()
        other_session = tokens_for(user)["refresh"]
        stolen = tokens_for(user)["refresh"]

        def post(token: str):
            return client.post(
                path, json.dumps({"refresh": token}), content_type="application/json"
            )

        rotated = post(stolen)
        assert rotated.status_code == 200
        _age_blacklist_past_grace()

        # The rotated token comes back: 401, and the whole user is revoked.
        assert post(stolen).status_code == 401
        assert post(rotated.json()["refresh"]).status_code == 401
        assert post(other_session).status_code == 401

    def test_replay_inside_grace_window_keeps_the_session(self, client):
        """A second tab sending the same cookie right after a rotation gets
        401, but the successor and other sessions stay valid."""
        user = UserFactory()
        other_session = tokens_for(user)["refresh"]
        shared = tokens_for(user)["refresh"]
        first = refresh(client, shared)
        assert first.status_code == 200
        assert refresh(client, shared).status_code == 401
        assert refresh(client, first.json()["refresh"]).status_code == 200
        assert refresh(client, other_session).status_code == 200

    def test_reuse_does_not_revoke_other_users(self, client):
        victim, bystander = UserFactory(), UserFactory()
        stolen = tokens_for(victim)["refresh"]
        bystander_refresh = tokens_for(bystander)["refresh"]
        assert refresh(client, stolen).status_code == 200
        _age_blacklist_past_grace()
        assert refresh(client, stolen).status_code == 401
        assert refresh(client, bystander_refresh).status_code == 200

    def test_password_change_revokes_refresh_tokens(self, client):
        user = UserFactory()
        before = tokens_for(user)["refresh"]
        user.set_password("N3w-Passw0rd!x")
        user.save()
        assert refresh(client, before).status_code == 401
        # Tokens issued after the change work.
        assert refresh(client, tokens_for(user)["refresh"]).status_code == 200

    def test_saving_without_password_change_keeps_tokens(self, client):
        user = UserFactory()
        token = tokens_for(user)["refresh"]
        user.first_name = "Renamed"
        user.save()
        assert refresh(client, token).status_code == 200

    def test_deactivated_user_cannot_refresh(self, client):
        user = UserFactory()
        token = tokens_for(user)["refresh"]
        user.is_active = False
        user.save()
        assert refresh(client, token).status_code == 401


@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="Needs Postgres row locks (scripts/test_ai_db.py runs it).",
)
@pytest.mark.django_db(transaction=True)
def test_concurrent_refresh_of_one_token_keeps_the_session():
    """Two tabs refresh the same cookie at once: one rotation wins, the other
    gets 401, and nothing is revoked."""
    user = UserFactory()
    shared = tokens_for(user)["refresh"]
    barrier = threading.Barrier(2)
    responses: list = []

    def tab() -> None:
        try:
            barrier.wait()
            responses.append(refresh(Client(), shared))
        finally:
            connection.close()

    threads = [threading.Thread(target=tab) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(r.status_code for r in responses) == [200, 401]
    winner = next(r for r in responses if r.status_code == 200)
    assert refresh(Client(), winner.json()["refresh"]).status_code == 200


class TestLogoutRevocation:
    def test_logout_blacklists_refresh_token(self, client):
        user = UserFactory()
        tokens = tokens_for(user)
        access, token = tokens["token"], tokens["refresh"]

        assert logout(client, access, token).status_code == 200

        # The blacklisted refresh token can no longer mint access tokens.
        assert refresh(client, token).status_code == 401

    @pytest.mark.parametrize("token", ["invalid", ""])
    def test_malformed_refresh_is_unauthorized(self, token):
        client = Client(enforce_csrf_checks=True)
        assert refresh(client, token).status_code == 401

    def test_production_cookies_are_secure(self, settings):
        from django.http import HttpResponse
        from core.security.cookie_auth import set_auth_cookies

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
