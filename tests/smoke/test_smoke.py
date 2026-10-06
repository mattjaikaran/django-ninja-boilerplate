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
