"""Smoke test fixtures.

Provides a minimal client and auth helpers for the smoke test suite.
Each smoke test creates its own data and is self-contained.
"""

import json

import pytest
from django.test import Client
from ninja_jwt.tokens import RefreshToken

from core.tests.factories import UserFactory
from todos.tests.factories import TodoFactory


@pytest.fixture
def smoke_client():
    """Plain Django test client — used for unauthenticated requests."""
    return Client()


@pytest.fixture
def smoke_user(db):
    """Create a fresh user for use in smoke tests."""
    return UserFactory()


@pytest.fixture
def smoke_auth_headers(smoke_user):
    """JWT auth headers for the smoke user."""
    refresh = RefreshToken.for_user(smoke_user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.fixture
def smoke_refresh_token(smoke_user):
    """Raw refresh token string for the smoke user."""
    refresh = RefreshToken.for_user(smoke_user)
    return str(refresh)


@pytest.fixture
def smoke_todo(smoke_user):
    """Create a todo owned by the smoke user."""
    return TodoFactory(user=smoke_user)


def post_json(client: Client, path: str, data: dict, **headers) -> object:
    """POST JSON helper that keeps tests concise."""
    return client.post(
        path,
        data=json.dumps(data),
        content_type="application/json",
        **headers,
    )


def put_json(client: Client, path: str, data: dict, **headers) -> object:
    """PUT JSON helper."""
    return client.put(
        path,
        data=json.dumps(data),
        content_type="application/json",
        **headers,
    )
