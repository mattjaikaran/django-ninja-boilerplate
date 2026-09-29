"""Behaviour tests for the unified health and metrics endpoints.

Covers the real routes (liveness/readiness/detailed/component/metrics), the
staff-JWT gate, dependency failure/recovery, and the 503 response contract.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ninja_jwt.tokens import RefreshToken

from api.urls import api
from core.observability.health import (
    HealthCheckResult,
    HealthStatus,
    get_health_checker,
)


def _auth_headers(user) -> dict[str, str]:
    """Return a Bearer JWT header for the given user."""
    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.fixture
def staff_auth(staff_user):
    return _auth_headers(staff_user)


@pytest.fixture
def user_auth(user):
    return _auth_headers(user)


def _healthy(name: str):
    def _check() -> HealthCheckResult:
        return HealthCheckResult(name=name, status=HealthStatus.HEALTHY, message="ok")

    return _check


def _unhealthy(name: str):
    def _check() -> HealthCheckResult:
        return HealthCheckResult(
            name=name, status=HealthStatus.UNHEALTHY, message="down"
        )

    return _check


# =============================================================================
# Liveness and basic health (public)
# =============================================================================


class TestLivenessAndBasic:
    def test_liveness_is_public_and_alive(self, api_client):
        response = api_client.get("/api/health/liveness")
        assert response.status_code == 200
        assert response.json()["alive"] is True

    def test_liveness_probes_nothing(self, api_client, django_assert_num_queries):
        """The liveness probe performs no DB or cache I/O."""
        from django.core.cache import cache

        with (
            patch.object(
                cache, "get", side_effect=AssertionError("cache read during liveness")
            ),
            patch.object(
                cache, "set", side_effect=AssertionError("cache write during liveness")
            ),
            django_assert_num_queries(0),
        ):
            response = api_client.get("/api/health/liveness")
        assert response.status_code == 200
        assert response.json()["alive"] is True

    def test_basic_health_is_public(self, api_client):
        response = api_client.get("/api/health/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


# =============================================================================
# Readiness (public, DB + cache only, 200/503)
# =============================================================================


class TestReadiness:
    def test_readiness_is_ready_when_deps_up(self, api_client):
        response = api_client.get("/api/health/readiness")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert set(body["checks"]) == {"database", "cache"}

    def test_readiness_503_on_database_failure_and_recovers(self, api_client):
        assert api_client.get("/api/health/readiness").status_code == 200

        with patch.dict(
            get_health_checker()._checks, {"database": _unhealthy("database")}
        ):
            response = api_client.get("/api/health/readiness")
            assert response.status_code == 503
            body = response.json()
            assert body["ready"] is False
            assert body["checks"]["database"] == "unhealthy"

        # patch.dict restores the real check, so the instance recovers.
        assert api_client.get("/api/health/readiness").status_code == 200


# =============================================================================
# Detailed (staff JWT, 200/503)
# =============================================================================


class TestDetailed:
    def test_detailed_requires_auth(self, api_client):
        assert api_client.get("/api/health/detailed").status_code == 401

    def test_detailed_rejects_non_staff(self, api_client, user_auth):
        assert api_client.get("/api/health/detailed", **user_auth).status_code == 403

    def test_detailed_200_when_all_checks_healthy(self, api_client, staff_auth):
        checker = get_health_checker()
        original = dict(checker._checks)
        try:
            for name in list(checker._checks):
                checker._checks[name] = _healthy(name)
            response = api_client.get("/api/health/detailed", **staff_auth)
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "healthy"
            assert "checks" in body
        finally:
            checker._checks.clear()
            checker._checks.update(original)

    def test_detailed_503_when_dependency_unhealthy(self, api_client, staff_auth):
        checker = get_health_checker()
        original = dict(checker._checks)
        try:
            for name in list(checker._checks):
                checker._checks[name] = _healthy(name)
            checker._checks["database"] = _unhealthy("database")
            response = api_client.get("/api/health/detailed", **staff_auth)
            assert response.status_code == 503
            assert response.json()["status"] == "unhealthy"
        finally:
            checker._checks.clear()
            checker._checks.update(original)


# =============================================================================
# Component (staff JWT, 200/503)
# =============================================================================


class TestComponent:
    def test_component_requires_auth(self, api_client):
        assert api_client.get("/api/health/component/database").status_code == 401

    def test_component_rejects_non_staff(self, api_client, user_auth):
        response = api_client.get("/api/health/component/database", **user_auth)
        assert response.status_code == 403

    def test_component_healthy(self, api_client, staff_auth):
        response = api_client.get("/api/health/component/database", **staff_auth)
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_component_unknown_returns_503(self, api_client, staff_auth):
        response = api_client.get("/api/health/component/does-not-exist", **staff_auth)
        assert response.status_code == 503
        assert response.json()["status"] == "unknown"


# =============================================================================
# Metrics (staff JWT, Prometheus text)
# =============================================================================


class TestMetrics:
    def test_metrics_requires_auth(self, api_client):
        assert api_client.get("/api/metrics").status_code == 401

    def test_metrics_rejects_non_staff(self, api_client, user_auth):
        assert api_client.get("/api/metrics", **user_auth).status_code == 403

    def test_metrics_returns_prometheus_text_for_staff(self, api_client, staff_auth):
        response = api_client.get("/api/metrics", **staff_auth)
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/plain")
        assert b"http_requests_total" in response.content


# =============================================================================
# OpenAPI schema agreement (runtime 503 must be declared)
# =============================================================================


class TestOpenAPISchema:
    def test_503_declared_for_dependency_probes(self):
        """The 503 responses the probes return are declared in the schema."""
        paths = api.get_openapi_schema()["paths"]

        assert 503 in paths["/api/health/readiness"]["get"]["responses"]
        assert 503 in paths["/api/health/detailed"]["get"]["responses"]
        assert 503 in paths["/api/health/component/{component}"]["get"]["responses"]

    def test_liveness_and_basic_stay_200_only(self):
        paths = api.get_openapi_schema()["paths"]

        assert set(paths["/api/health/liveness"]["get"]["responses"]) == {200}
        assert set(paths["/api/health/"]["get"]["responses"]) == {200}
