"""Global pytest configuration and fixtures.

This module provides shared fixtures for all tests in the project.
Individual apps can have their own conftest.py files for app-specific fixtures.
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings.test")
django.setup()

import pytest
from django.test import Client
from ninja.testing import TestClient

from api.urls import api

# =============================================================================
# Collection Configuration
# =============================================================================

# Skip collecting test-like files in management commands, migrations, and CLI
collect_ignore_glob = [
    "*/management/commands/*",
    "*/migrations/*",
    "cli/*",
    "deploy/*",
    "scripts/*",
]

# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Give all tests access to the database.

    This fixture automatically applies to all tests and ensures database access.
    """


@pytest.fixture
def transactional_db(db):
    """Create a transactional database for tests that need transaction testing."""


# =============================================================================
# Client Fixtures
# =============================================================================


@pytest.fixture
def api_client():
    """Return Django test client for API testing."""
    return Client()


@pytest.fixture
def ninja_client():
    """Return Django Ninja test client for API testing.

    This client is specifically designed for testing Django Ninja endpoints
    and provides better integration with the Ninja API.
    """
    return TestClient(api)


# =============================================================================
# Convenience API Test Client
# =============================================================================


class APITestClient:
    """Wrapper around Django's test client that handles /api/ prefix and auth.

    Usage:
        def test_list_users(api):
            response = api.get("/users/")  # Automatically prefixed with /api
            assert response.status_code == 200
    """

    def __init__(self, client: Client, prefix: str = "/api"):
        self.client = client
        self.prefix = prefix
        self._headers: dict = {}

    def authenticate(self, user):
        """Set JWT auth headers for the given user."""
        from ninja_jwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        self._headers["HTTP_AUTHORIZATION"] = f"Bearer {refresh.access_token}"
        return self

    def _url(self, path: str) -> str:
        if path.startswith(self.prefix):
            return path
        return f"{self.prefix}{path}"

    def get(self, path, **kwargs):
        return self.client.get(self._url(path), **{**self._headers, **kwargs})

    def post(self, path, data=None, content_type="application/json", **kwargs):
        return self.client.post(
            self._url(path),
            data=data,
            content_type=content_type,
            **{**self._headers, **kwargs},
        )

    def put(self, path, data=None, content_type="application/json", **kwargs):
        return self.client.put(
            self._url(path),
            data=data,
            content_type=content_type,
            **{**self._headers, **kwargs},
        )

    def patch(self, path, data=None, content_type="application/json", **kwargs):
        return self.client.patch(
            self._url(path),
            data=data,
            content_type=content_type,
            **{**self._headers, **kwargs},
        )

    def delete(self, path, **kwargs):
        return self.client.delete(self._url(path), **{**self._headers, **kwargs})


@pytest.fixture
def api_test_client():
    """Return an APITestClient for convenient API testing."""
    return APITestClient(Client())


@pytest.fixture
def authenticated_api_client(user):
    """Return an authenticated APITestClient."""
    client = APITestClient(Client())
    client.authenticate(user)
    return client


# =============================================================================
# User Fixtures
# =============================================================================


@pytest.fixture
def user(db):
    """Create a regular user for testing.

    Returns:
        User: A regular (non-staff, non-superuser) test user
    """
    from core.tests.factories import UserFactory

    return UserFactory()


@pytest.fixture
def staff_user(db):
    """Create a staff user for testing.

    Returns:
        User: A staff (admin access) test user
    """
    from core.tests.factories import UserFactory

    return UserFactory(is_staff=True)


@pytest.fixture
def superuser(db):
    """Create a superuser for testing.

    Returns:
        User: A superuser with all permissions
    """
    from core.tests.factories import UserFactory

    return UserFactory(is_staff=True, is_superuser=True)


@pytest.fixture
def verified_user(db):
    """Create a verified user for testing.

    Returns:
        User: A verified test user
    """
    from core.tests.factories import UserFactory

    return UserFactory(is_verified=True)


# =============================================================================
# Authentication Fixtures
# =============================================================================


@pytest.fixture
def auth_headers(user):
    """Get authentication headers for a user.

    Returns:
        dict: Headers with JWT token for authenticated requests
    """
    from ninja_jwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.fixture
def authenticated_client(api_client, user, auth_headers):
    """Return an authenticated Django test client.

    Returns:
        tuple: (Client, User) - Client with auth headers and the user
    """
    api_client.defaults.update(auth_headers)
    return api_client, user


@pytest.fixture
def authenticated_ninja_client(ninja_client, user):
    """Return an authenticated Ninja test client.

    Returns:
        tuple: (TestClient, User) - Client with auth and the user
    """
    from ninja_jwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    ninja_client.headers = {"Authorization": f"Bearer {refresh.access_token}"}
    return ninja_client, user


# =============================================================================
# Todo Fixtures (Example)
# =============================================================================


@pytest.fixture
def todo(user):
    """Create a todo for testing.

    Returns:
        Todo: A test todo instance
    """
    from todos.tests.factories import TodoFactory

    return TodoFactory(user=user)


@pytest.fixture
def todo_list(user):
    """Create a list of todos for testing.

    Returns:
        list[Todo]: List of 5 test todo instances
    """
    from todos.tests.factories import TodoFactory

    return TodoFactory.create_batch(5, user=user)


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def freezer():
    """Freeze time for testing.

    Usage:
        def test_something(freezer):
            freezer.move_to("2024-01-01")
            # Time is now frozen at 2024-01-01

    Note: Requires pytest-freezegun to be installed
    """
    pytest.importorskip("freezegun")
    from freezegun import freeze_time

    return freeze_time


@pytest.fixture
def mock_email_backend(settings):
    """Use in-memory email backend for testing.

    This prevents actual emails from being sent during tests.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail

    mail.outbox = []
    return mail


@pytest.fixture
def temp_media(settings, tmp_path):
    """Use temporary directory for media files during testing.

    Returns:
        Path: Temporary media root directory
    """
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    return settings.MEDIA_ROOT


# =============================================================================
# Performance Testing Fixtures
# =============================================================================


@pytest.fixture
def assert_num_queries(django_assert_num_queries):
    """Assert the number of database queries.

    Usage:
        def test_efficient_query(assert_num_queries):
            with assert_num_queries(1):
                list(MyModel.objects.all())
    """
    return django_assert_num_queries


# =============================================================================
# Marker Definitions
# =============================================================================

# These markers can be used to categorize tests:
# @pytest.mark.slow - for slow tests
# @pytest.mark.integration - for integration tests
# @pytest.mark.unit - for unit tests
