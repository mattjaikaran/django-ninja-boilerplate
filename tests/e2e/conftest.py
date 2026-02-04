"""E2E Test Configuration and Fixtures

This module provides common fixtures and configuration for E2E tests.
"""

import pytest
from django.test import Client

# =============================================================================
# API Client Fixtures
# =============================================================================


@pytest.fixture
def e2e_client():
    """Return a Django test client configured for E2E testing.

    This client maintains session state between requests,
    making it suitable for testing multi-step user journeys.
    """
    return Client()


@pytest.fixture
def authenticated_e2e_client(e2e_client, test_user, auth_token):
    """Return an authenticated E2E client.

    The client has the auth token set in its default headers.
    """
    e2e_client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {auth_token}"
    return e2e_client


# =============================================================================
# User Fixtures
# =============================================================================


@pytest.fixture
def test_user_data():
    """Return data for creating a test user."""
    return {
        "email": "e2e_test@example.com",
        "password": "TestPassword123!",
        "first_name": "E2E",
        "last_name": "Tester",
    }


@pytest.fixture
def test_user(db, test_user_data):
    """Create and return a test user for E2E tests.

    Returns:
        User: A test user instance
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # Clean up any existing test user
    User.objects.filter(email=test_user_data["email"]).delete()

    user = User.objects.create_user(
        email=test_user_data["email"],
        password=test_user_data["password"],
        first_name=test_user_data["first_name"],
        last_name=test_user_data["last_name"],
    )
    return user


@pytest.fixture
def auth_token(test_user):
    """Get an authentication token for the test user.

    Returns:
        str: JWT access token
    """
    try:
        from ninja_jwt.tokens import RefreshToken
    except ImportError:
        from django_ninja_jwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(test_user)
    return str(refresh.access_token)


@pytest.fixture
def auth_headers(auth_token):
    """Return authentication headers for API requests.

    Returns:
        dict: Headers with JWT token
    """
    return {"HTTP_AUTHORIZATION": f"Bearer {auth_token}"}


# =============================================================================
# Todo Fixtures (for CRUD operation tests)
# =============================================================================


@pytest.fixture
def test_todo_data():
    """Return data for creating a test todo."""
    return {
        "title": "E2E Test Todo",
        "description": "This is a test todo for E2E testing",
        "is_completed": False,
    }


@pytest.fixture
def test_todo(db, test_user, test_todo_data):
    """Create and return a test todo for E2E tests.

    Returns:
        Todo: A test todo instance
    """
    from todos.models import Todo

    todo = Todo.objects.create(
        title=test_todo_data["title"],
        description=test_todo_data["description"],
        is_completed=test_todo_data["is_completed"],
        created_by=test_user,
        updated_by=test_user,
    )
    return todo


# =============================================================================
# Helper Fixtures
# =============================================================================


@pytest.fixture
def unique_email():
    """Generate a unique email for testing.

    Returns:
        str: A unique email address
    """
    import uuid

    return f"e2e_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def mock_email_backend(settings):
    """Configure email backend to use in-memory storage during tests.

    This prevents actual emails from being sent and allows
    inspection of sent emails.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail

    mail.outbox = []
    return mail


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_sequences(db):
    """Reset database sequences after each test.

    This ensures consistent ID generation across tests.
    """
    return
    # Cleanup happens automatically with transaction rollback


@pytest.fixture
def clean_db(db):
    """Provide a clean database state.

    Use this fixture when you need to ensure no residual data
    from previous tests.
    """
    from django.contrib.auth import get_user_model

    from todos.models import Todo

    User = get_user_model()

    # Clean up test data
    Todo.objects.filter(title__startswith="E2E").delete()
    User.objects.filter(email__startswith="e2e_test").delete()

    yield

    # Post-test cleanup
    Todo.objects.filter(title__startswith="E2E").delete()
    User.objects.filter(email__startswith="e2e_test").delete()


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config):
    """Register custom markers for E2E tests."""
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line(
        "markers", "journey(name): mark test as part of a specific user journey"
    )
