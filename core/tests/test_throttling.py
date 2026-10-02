"""Throttling behaviour tests.

Covers rate-limit buckets, 429 retry metadata, trusted/untrusted proxy chain
behaviour, spoof resistance, unthrottled probes, and the intact brute-force
login lockout.
"""

from __future__ import annotations

import json

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory
from ninja.errors import Throttled
from ninja_extra.conf import settings as ninja_extra_settings
from ninja_extra.throttling import DynamicRateThrottle, UserRateThrottle

from api.urls import handle_throttled


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate throttle buckets between tests (LocMemCache is process-global)."""
    cache.clear()
    yield
    cache.clear()


def _request(remote_addr: str = "127.0.0.1", xff: str | None = None):
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    request.META["REMOTE_ADDR"] = remote_addr
    if xff is not None:
        request.META["HTTP_X_FORWARDED_FOR"] = xff
    return request


# =============================================================================
# Buckets
# =============================================================================


class TestBuckets:
    def test_throttle_allows_up_to_limit_then_denies(self):
        throttle = DynamicRateThrottle(rate="3/min", scope="test")
        request = _request()

        for _ in range(3):
            assert throttle.allow_request(request) is True

        assert throttle.allow_request(request) is False

    def test_throttle_wait_reports_retry_delay(self):
        throttle = DynamicRateThrottle(rate="2/min", scope="test")
        request = _request()

        throttle.allow_request(request)
        throttle.allow_request(request)

        assert throttle.allow_request(request) is False
        assert throttle.wait() is not None
        assert throttle.wait() > 0


# =============================================================================
# 429 retry metadata
# =============================================================================


class TestRetryMetadata:
    def test_handle_throttled_sets_retry_after_header(self):
        response = handle_throttled(_request(), Throttled(wait=42.7))
        assert response.status_code == 429
        assert response["Retry-After"] == "43"  # ceil(42.7)

    def test_handle_throttled_embeds_retry_after_in_body(self):
        response = handle_throttled(_request(), Throttled(wait=9.0))
        body = json.loads(response.content)
        assert body["retry_after"] == 9

    def test_handle_throttled_falls_back_when_wait_is_none(self):
        response = handle_throttled(_request(), Throttled(wait=None))
        assert response.status_code == 429
        assert response["Retry-After"] == "1"


# =============================================================================
# Trusted proxy chain + spoof resistance
# =============================================================================


class TestTrustedProxyChain:
    def test_zero_proxies_uses_remote_addr_and_ignores_xff(self, monkeypatch):
        monkeypatch.setattr(ninja_extra_settings, "NUM_PROXIES", 0)
        throttle = UserRateThrottle()
        request = _request(remote_addr="1.2.3.4", xff="9.9.9.9, 8.8.8.8")
        assert throttle.get_ident(request) == "1.2.3.4"

    def test_one_proxy_uses_last_xff_entry(self, monkeypatch):
        monkeypatch.setattr(ninja_extra_settings, "NUM_PROXIES", 1)
        throttle = UserRateThrottle()
        request = _request(remote_addr="10.0.0.1", xff="forged, 5.6.7.8")
        assert throttle.get_ident(request) == "5.6.7.8"

    def test_attacker_prepended_xff_is_ignored(self, monkeypatch):
        # The trusted proxy appends the real client; the forged first hop
        # must never mint a fresh bucket.
        monkeypatch.setattr(ninja_extra_settings, "NUM_PROXIES", 1)
        throttle = UserRateThrottle()
        request = _request(remote_addr="10.0.0.1", xff="6.6.6.6, 5.6.7.8")
        assert throttle.get_ident(request) == "5.6.7.8"

    def test_clients_behind_one_proxy_get_separate_buckets(self, monkeypatch):
        # Every request arrives from nginx's address. With one trusted proxy,
        # an exhausted client must not block the next one.
        monkeypatch.setattr(ninja_extra_settings, "NUM_PROXIES", 1)
        throttle = DynamicRateThrottle(rate="2/min", scope="anon-auth")
        first = _request(remote_addr="172.18.0.5", xff="198.51.100.7")
        second = _request(remote_addr="172.18.0.5", xff="198.51.100.8")
        assert throttle.allow_request(first) is True
        assert throttle.allow_request(first) is True
        assert throttle.allow_request(first) is False
        assert throttle.allow_request(second) is True


# =============================================================================
# Unthrottled probes
# =============================================================================


class TestUnthrottledProbes:
    def test_health_probes_are_not_throttled(self, api_client):
        # Liveness and readiness carry no throttle; hammering them never 429s.
        for _ in range(50):
            assert api_client.get("/api/health/liveness").status_code == 200
            assert api_client.get("/api/health/readiness").status_code == 200

    def test_metrics_is_not_throttled(self, api_client):
        # Metrics is staff-gated but not throttled; anonymous gets 401, never 429.
        for _ in range(20):
            assert api_client.get("/api/metrics").status_code == 401


# =============================================================================
# Intact brute-force login lockout
# =============================================================================


class TestLoginLockoutIntact:
    def test_lockout_after_five_failed_attempts(self, api_client, user):
        payload = {"email": user.email, "password": "definitely-wrong"}

        for _ in range(5):
            response = api_client.post(
                "/api/auth/login", payload, content_type="application/json"
            )
            assert response.status_code == 400

        # The sixth attempt is rejected by the brute-force lockout.
        response = api_client.post(
            "/api/auth/login", payload, content_type="application/json"
        )
        assert response.status_code == 429
