import pytest
from django.test import Client


@pytest.fixture
def api_client():
    """Return Django test client for API testing."""
    return Client()


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Give all tests access to the database.

    This fixture automatically applies to all tests and ensures database access.
    """


@pytest.fixture
def transactional_db(db):
    """Create a transactional database for tests that need transaction testing."""
