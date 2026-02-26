"""Smoke test suite.

Hits every major endpoint once and asserts the expected HTTP status code.
No response body assertions — just verify the API is alive and routing correctly.

Run:
    uv run pytest tests/smoke/ -v --no-header -p no:warnings -m smoke
"""

import uuid

import pytest

from todos.tests.factories import TodoFactory

from .conftest import post_json, put_json

# =============================================================================
# Health
# =============================================================================


@pytest.mark.smoke
@pytest.mark.django_db
def test_health_check(smoke_client):
    """GET /api/health/ returns 200."""
    response = smoke_client.get("/api/health/")
    assert response.status_code == 200


# =============================================================================
# Auth — registration
# =============================================================================


@pytest.mark.smoke
@pytest.mark.django_db
def test_auth_register(smoke_client):
    """POST /api/auth/signup returns 201."""
    uid = uuid.uuid4().hex[:8]
    payload = {
        "email": f"smoke_{uid}@example.com",
        "username": f"smoke_{uid}",
        "password": "SmokePass1!",
        "first_name": "Smoke",
        "last_name": "User",
    }
    response = post_json(smoke_client, "/api/auth/signup", payload)
    assert response.status_code == 201


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
# Auth — JWT token refresh
# =============================================================================


@pytest.mark.smoke
@pytest.mark.django_db
def test_auth_token_refresh(smoke_client, smoke_refresh_token):
    """POST /api/token/refresh returns 200 with new access token."""
    payload = {"refresh": smoke_refresh_token}
    response = post_json(smoke_client, "/api/token/refresh", payload)
    assert response.status_code == 200
    data = response.json()
    assert "access" in data


# =============================================================================
# Auth — current user
# =============================================================================


@pytest.mark.smoke
@pytest.mark.django_db
def test_auth_me(smoke_client, smoke_user):
    """GET /api/auth/me returns 200 for authenticated user.

    AuthController has no JWTAuth on the controller — the endpoint checks
    request.user.is_authenticated directly.  Use force_login to establish a
    Django session so the middleware sets request.user correctly.
    """
    smoke_client.force_login(smoke_user)
    response = smoke_client.get("/api/auth/me")
    assert response.status_code == 200


# =============================================================================
# Todos — primary controller (/api/todos/)
# =============================================================================


@pytest.mark.smoke
@pytest.mark.django_db
def test_todos_list(smoke_client, smoke_auth_headers):
    """GET /api/todos/ returns 200."""
    response = smoke_client.get("/api/todos/", **smoke_auth_headers)
    assert response.status_code == 200


@pytest.mark.smoke
@pytest.mark.django_db
def test_todos_create(smoke_client, smoke_auth_headers):
    """POST /api/todos/ returns 201."""
    payload = {
        "title": "Smoke test todo",
        "description": "Created by smoke tests",
        "completed": False,
    }
    response = post_json(smoke_client, "/api/todos/", payload, **smoke_auth_headers)
    assert response.status_code == 201


@pytest.mark.smoke
@pytest.mark.django_db
def test_todos_get(smoke_client, smoke_user, smoke_auth_headers):
    """GET /api/todos/{id} returns 200."""
    todo = TodoFactory(user=smoke_user)
    response = smoke_client.get(f"/api/todos/{todo.id}", **smoke_auth_headers)
    assert response.status_code == 200


@pytest.mark.smoke
@pytest.mark.django_db
def test_todos_update(smoke_client, smoke_user, smoke_auth_headers):
    """PUT /api/todos/{id} returns 200."""
    todo = TodoFactory(user=smoke_user)
    payload = {
        "title": "Updated smoke title",
        "description": "Updated by smoke tests",
        "completed": True,
    }
    response = put_json(
        smoke_client, f"/api/todos/{todo.id}", payload, **smoke_auth_headers
    )
    assert response.status_code == 200


@pytest.mark.smoke
@pytest.mark.django_db
def test_todos_delete(smoke_client, smoke_user, smoke_auth_headers):
    """DELETE /api/todos/{id} returns 204."""
    todo = TodoFactory(user=smoke_user)
    response = smoke_client.delete(f"/api/todos/{todo.id}", **smoke_auth_headers)
    assert response.status_code == 204


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
