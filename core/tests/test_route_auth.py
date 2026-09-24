"""Route-level authentication and authorization regression tests.

These tests lock down the public/protected route contract (slice 1) and the
JWT/role permission matrix (slice 2):

- Anonymous requests to sensitive routes return 401.
- Authenticated non-staff requests to staff routes return 403.
- Staff and superuser success paths pass.
- Public auth operations (login/signup/...) remain reachable without a token.
- The OpenAPI schema declares bearer security only on protected operations.
"""

import json

import pytest
from django.test import Client
from ninja_jwt.tokens import RefreshToken

from core.tests.factories import UserFactory

User = pytest.importorskip("django.contrib.auth").get_user_model()


def bearer_for(user) -> dict:
    """Build Django test-client auth headers for *user*."""
    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


def post_json(client: Client, path: str, data: dict, **headers) -> object:
    return client.post(path, json.dumps(data), content_type="application/json", **headers)


# =============================================================================
# Slice 1 — anonymous regression: sensitive routes are 401, public stay open
# =============================================================================


@pytest.mark.django_db
class TestAnonymousRouteContract:
    """Anonymous requests to protected routes must return 401."""

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.mark.parametrize(
        "method,path,body",
        [
            ("get", "/api/auth/me", None),
            ("get", "/api/auth/status", None),
            ("post", "/api/auth/logout", {}),
            ("get", "/api/users/", None),
            ("post", "/api/users/superuser", {}),
            ("get", "/api/tasks/stats", None),
            ("get", "/api/tasks/recent", None),
            ("get", "/api/tasks/scheduler/", None),
            ("get", "/api/tasks/dlq/", None),
            ("get", "/api/audit/", None),
            ("post", "/api/decisions/evaluate", {}),
            ("get", "/api/api-keys/", None),
        ],
    )
    def test_protected_routes_reject_anonymous(self, client, method, path, body):
        if method == "get":
            response = client.get(path)
        else:
            response = post_json(client, path, body)
        assert response.status_code == 401, f"{method.upper()} {path} -> {response.status_code}"

    @pytest.mark.parametrize(
        "method,path",
        [
            ("post", "/api/auth/login"),
            ("post", "/api/auth/login/username"),
            ("post", "/api/auth/signup"),
            ("post", "/api/auth/passwordless/login/request"),
            ("post", "/api/auth/passwordless/login/verify"),
        ],
    )
    def test_public_auth_operations_reach_handler(self, client, method, path):
        """Public auth ops must not be blocked by JWTAuth (4xx from validation is fine)."""
        response = post_json(client, path, {"email": "x@example.com"})
        assert response.status_code != 401, f"{path} was wrongly protected"


# =============================================================================
# Slice 2 — role permissions: staff/superuser matrix
# =============================================================================


@pytest.mark.django_db
class TestRolePermissions:
    """Role-based authorization on staff and superuser routes."""

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def regular_user(self):
        return UserFactory()

    @pytest.fixture
    def staff_user(self):
        return UserFactory(is_staff=True)

    @pytest.fixture
    def superuser(self):
        return UserFactory(is_staff=True, is_superuser=True)

    @pytest.mark.parametrize(
        "method,path",
        [
            ("get", "/api/users/"),
            ("get", "/api/users/staff"),
            ("get", "/api/users/active"),
            ("get", "/api/tasks/scheduler/"),
            ("get", "/api/tasks/scheduler/stats"),
            ("get", "/api/tasks/dlq/"),
            ("get", "/api/audit/"),
            ("get", "/api/audit/stats/summary"),
        ],
    )
    def test_staff_routes_forbid_regular_user(self, client, regular_user, method, path):
        response = client.get(path, **bearer_for(regular_user))
        assert response.status_code == 403, f"{path} -> {response.status_code}"

    @pytest.mark.parametrize(
        "path",
        [
            "/api/users/",
            "/api/tasks/scheduler/",
            "/api/tasks/dlq/",
            "/api/audit/",
        ],
    )
    def test_staff_routes_allow_staff(self, client, staff_user, path):
        response = client.get(path, **bearer_for(staff_user))
        assert response.status_code == 200, f"{path} -> {response.status_code}"

    def test_superuser_creation_forbids_staff(self, client, staff_user):
        payload = {
            "username": "newadmin",
            "email": "newadmin@example.com",
            "password": "Str0ngPass!234",
            "first_name": "New",
            "last_name": "Admin",
        }
        response = post_json(
            client, "/api/users/superuser", payload, **bearer_for(staff_user)
        )
        assert response.status_code == 403

    def test_superuser_creation_allows_superuser(self, client, superuser):
        payload = {
            "username": "newadmin",
            "email": "newadmin@example.com",
            "password": "Str0ngPass!234",
            "first_name": "New",
            "last_name": "Admin",
        }
        response = post_json(
            client, "/api/users/superuser", payload, **bearer_for(superuser)
        )
        assert response.status_code == 201, response.content

    def test_task_status_allows_authenticated_user(self, client, regular_user):
        """Task status/progress is JWT-protected, not staff-only."""
        response = client.get("/api/tasks/stats", **bearer_for(regular_user))
        assert response.status_code == 200

    def test_decisions_requires_jwt_not_staff(self, client, regular_user):
        """Decisions requires JWT (anonymous is 401) but not staff."""
        response = post_json(
            client,
            "/api/decisions/evaluate",
            {"state": {}, "questions": [], "provider": "fake"},
            **bearer_for(regular_user),
        )
        # Auth passes (not 401/403); the remaining status is schema/business.
        assert response.status_code not in (401, 403)


# =============================================================================
# Slice 2 — OpenAPI security declarations
# =============================================================================


class TestOpenAPISecurity:
    """The OpenAPI schema must declare bearer security only on protected ops."""

    @pytest.fixture(scope="class")
    def schema(self):
        from api.urls import api

        return api.get_openapi_schema()

    def _operation(self, schema, path, method):
        ops = schema["paths"][path]
        return ops[method]

    @pytest.mark.parametrize(
        "method,path",
        [
            ("get", "/api/auth/me"),
            ("get", "/api/auth/status"),
            ("post", "/api/auth/logout"),
            ("get", "/api/users/"),
            ("post", "/api/users/superuser"),
            ("get", "/api/tasks/stats"),
            ("get", "/api/tasks/scheduler/"),
            ("get", "/api/tasks/dlq/"),
            ("get", "/api/audit/"),
            ("post", "/api/decisions/evaluate"),
        ],
    )
    def test_protected_operations_declare_security(self, schema, method, path):
        op = self._operation(schema, path, method)
        assert op.get("security"), f"{method.upper()} {path} missing security"

    @pytest.mark.parametrize(
        "method,path",
        [
            ("post", "/api/auth/login"),
            ("post", "/api/auth/signup"),
            ("post", "/api/auth/passwordless/login/request"),
        ],
    )
    def test_public_operations_have_no_security(self, schema, method, path):
        op = self._operation(schema, path, method)
        assert not op.get("security"), f"{method.upper()} {path} should be public"

    def test_bearer_scheme_is_declared(self, schema):
        schemes = schema.get("components", {}).get("securitySchemes", {})
        assert "JWTAuth" in schemes
        assert schemes["JWTAuth"]["scheme"] == "bearer"
