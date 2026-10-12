"""Redis/Valkey cache generator templates.

The app works through Django's cache framework, so it uses whatever backend
``CACHES`` in ``api/settings`` builds from ``REDIS_URL``/``VALKEY_URL``
(``valkey://`` included) and the in-memory cache of the test settings. Every
template is verbatim code: ``fill_imports`` puts the app's isort block where
``{first_party_imports}`` stands.
"""

CACHE_SCHEMAS_TEMPLATE = '''"""Cache schemas."""

from core.schemas.base_schema import CamelCaseSchema


class CacheHealthSchema(CamelCaseSchema):
    """Result of a write, read and delete round trip against a cache."""

    backend: str
    round_trip_ms: float
'''

CACHE_SERVICE_TEMPLATE = '''"""Cache operations for staff tooling.

Application code reads and writes the cache through ``django.core.cache``.
This service adds the operations staff run by hand: a round-trip health check
and the removal of one stale key. Connection errors are not caught: they reach
the exception handlers as a 500 that carries the real error.
"""

import time
from uuid import uuid4

from django.core.cache import caches

{first_party_imports}

PROBE_PREFIX = "cache-health:"
PROBE_TIMEOUT = 10


class CacheService:
    """Health check and key removal for one configured cache alias."""

    def __init__(self, alias: str = "default"):
        self.cache = caches[alias]

    def health(self) -> dict[str, str | float]:
        """Write, read and delete a probe key. Return the backend and timing."""
        probe = f"{PROBE_PREFIX}{uuid4().hex}"
        started = time.perf_counter()
        self.cache.set(probe, probe, timeout=PROBE_TIMEOUT)
        stored = self.cache.get(probe)
        self.cache.delete(probe)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if stored != probe:
            raise ExternalServiceError("The cache did not return the value it stored")
        return {
            "backend": type(self.cache).__name__,
            "round_trip_ms": round(elapsed_ms, 3),
        }

    def delete(self, key: str) -> None:
        """Delete one key. Raise NotFoundError when the key is not cached."""
        if not self.cache.delete(key):
            raise NotFoundError(f"Cache key {key!r} not found")
'''

# Staff-only (IsAdminUser): cache keys can hold session data and tokens.
CACHE_CONTROLLER_TEMPLATE = '''"""Cache controller. Staff check cache health and remove stale keys."""

from ninja_extra import api_controller, http_delete, http_get
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/cache", tags=["Cache"], auth=JWTAuth(), permissions=[IsAdminUser])
class CacheController:
    """Staff-only cache operations on the default cache alias."""

    def __init__(self):
        self.service = CacheService()

    @http_get("/health", response={200: CacheHealthSchema, 502: dict})
    @log_api_call()
    def get_health(self, request):
        """Run a write, read and delete round trip against the cache."""
        return 200, self.service.health()

    @http_delete("/keys/{key}", response={204: None, 404: dict})
    @log_api_call()
    def delete_key(self, request, key: str):
        """Delete one cache key, for example a stale cached value."""
        self.service.delete(key)
        return 204, None
'''

# Staff 200/204, regular user 403, missing key 404. Uses the real cache
# backend of the test settings. The 403 test covers the controller-level
# permission that guards both routes.
CACHE_TESTS_TEMPLATE = '''"""Smoke and permission tests for the cache API."""

import pytest
from django.core.cache import cache, caches
from ninja_jwt.tokens import RefreshToken


@pytest.fixture
def staff_client(api_client, staff_user):
    token = RefreshToken.for_user(staff_user).access_token
    api_client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return api_client


@pytest.mark.django_db
class TestCacheAPI:
    """Staff check cache health and delete keys; other users get 403."""

    def test_staff_reads_health(self, staff_client):
        response = staff_client.get("/api/cache/health")
        assert response.status_code == 200
        assert response.json()["backend"] == type(caches["default"]).__name__

    def test_regular_user_cannot_read_health(self, authenticated_client):
        client, _ = authenticated_client
        response = client.get("/api/cache/health")
        assert response.status_code == 403

    def test_staff_deletes_key(self, staff_client):
        cache.set("stale-report", "old")
        response = staff_client.delete("/api/cache/keys/stale-report")
        assert response.status_code == 204
        assert cache.get("stale-report") is None

    def test_delete_missing_key_returns_404(self, staff_client):
        response = staff_client.delete("/api/cache/keys/never-cached")
        assert response.status_code == 404
'''
