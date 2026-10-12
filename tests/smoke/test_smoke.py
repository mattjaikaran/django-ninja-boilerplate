"""Smoke test suite.

Hits the endpoints that no app test covers and asserts the expected HTTP
status code. Health, signup, refresh, ``/auth/me`` and the primary todo CRUD
are covered in ``core/tests`` and ``todos/tests``; do not copy them here.

Run:
    uv run pytest tests/smoke/ -v --no-header -p no:warnings -m smoke
"""

import pytest

from .conftest import post_json

# =============================================================================
# Auth — JWT token pair (login)
# =============================================================================


@pytest.mark.smoke
@pytest.mark.django_db
def test_auth_token_pair(smoke_client, smoke_user):
    """POST /api/token/pair returns 200 with access + refresh tokens.

    NinjaJWT uses the model's USERNAME_FIELD (email) for authentication,
    not the 'username' column.
    """
    payload = {"email": smoke_user.email, "password": "testpass123"}
    response = post_json(smoke_client, "/api/token/pair", payload)
    assert response.status_code == 200
    data = response.json()
    assert "access" in data
    assert "refresh" in data


# =============================================================================
# Todos — basic controller (/api/todos-basic/)
# =============================================================================


@pytest.mark.smoke
@pytest.mark.django_db
def test_todos_basic_list(smoke_client, smoke_auth_headers):
    """GET /api/todos-basic/ returns 200."""
    response = smoke_client.get("/api/todos-basic/", **smoke_auth_headers)
    assert response.status_code == 200


# =============================================================================
# Todos — declarative controller (/api/todos-declarative/)
# =============================================================================


@pytest.mark.smoke
@pytest.mark.django_db
def test_todos_declarative_list(smoke_client, smoke_auth_headers):
    """GET /api/todos-declarative/ returns 200."""
    response = smoke_client.get("/api/todos-declarative/", **smoke_auth_headers)
    assert response.status_code == 200


# =============================================================================
# Todos — partial controller (/api/todos-partial/)
# =============================================================================


@pytest.mark.smoke
@pytest.mark.django_db
def test_todos_partial_list(smoke_client, smoke_auth_headers):
    """GET /api/todos-partial/ returns 200."""
    response = smoke_client.get("/api/todos-partial/", **smoke_auth_headers)
    assert response.status_code == 200


# =============================================================================
# Route sweep: every parameterless GET in the OpenAPI schema
# =============================================================================

# Routes that depend on an external service unavailable under test settings.
# Map the OpenAPI path to the reason it is skipped.
_SWEEP_EXCLUDED: dict[str, str] = {}


@pytest.mark.smoke
@pytest.mark.django_db
def test_get_route_sweep(smoke_client, smoke_auth_headers):
    """Every parameterless GET returns no 5xx and no 422 for a regular user."""
    from api.urls import api

    schema = api.get_openapi_schema()
    offenders: list[tuple[str, int]] = []
    for path, methods in schema["paths"].items():
        if "get" not in methods or "{" in path or path in _SWEEP_EXCLUDED:
            continue
        status = smoke_client.get(path, **smoke_auth_headers).status_code
        if status >= 500 or status == 422:
            offenders.append((path, status))
    assert offenders == []
