"""Contract test fixtures.

This module provides fixtures for API contract testing using schemathesis.
Contract tests validate that API responses conform to the OpenAPI specification.
"""

import os

import pytest


@pytest.fixture(scope="session")
def base_url():
    """Get the base URL for API testing.

    Returns the base URL where the API is running. Defaults to localhost:8000.
    Override with TEST_BASE_URL environment variable.
    """
    return os.environ.get("TEST_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def openapi_schema_url(base_url):
    """Get the OpenAPI schema URL.

    Returns the URL for the OpenAPI/Swagger schema endpoint.
    """
    return f"{base_url}/api/openapi.json"


@pytest.fixture(scope="session")
def api_docs_url(base_url):
    """Get the API documentation URL."""
    return f"{base_url}/api/docs"


@pytest.fixture
def auth_token_for_contract(base_url):
    """Get an authentication token for contract testing.

    This fixture creates a test user and returns a valid JWT token.
    For contract tests that require authentication.
    """
    import httpx

    # Try to login with test credentials or create a user
    test_email = "contract_test@example.com"
    test_password = "ContractTest123!"

    # First try to signup
    signup_response = httpx.post(
        f"{base_url}/api/auth/signup",
        json={
            "email": test_email,
            "password": test_password,
            "first_name": "Contract",
            "last_name": "Tester",
        },
        timeout=10,
    )

    # Then login (whether signup succeeded or user already exists)
    login_response = httpx.post(
        f"{base_url}/api/auth/login",
        json={"email": test_email, "password": test_password},
        timeout=10,
    )

    if login_response.status_code == 200:
        data = login_response.json()
        return data.get("access") or data.get("token")

    # Return None if we couldn't get a token
    return None


@pytest.fixture
def auth_headers_for_contract(auth_token_for_contract):
    """Get authorization headers for contract testing."""
    if auth_token_for_contract:
        return {"Authorization": f"Bearer {auth_token_for_contract}"}
    return {}


@pytest.fixture(scope="session")
def public_endpoints():
    """List of public endpoints that don't require authentication.

    These endpoints should be accessible without auth tokens.
    """
    return [
        "/api/health/",
        "/api/health/detailed/",
        "/api/auth/login",
        "/api/auth/signup",
        "/api/auth/passwordless/login/request",
        "/api/auth/otp/request",
    ]


@pytest.fixture(scope="session")
def protected_endpoints():
    """List of protected endpoints that require authentication.

    These endpoints need valid JWT tokens to access.
    """
    return [
        "/api/auth/me",
        "/api/auth/logout",
        "/api/users/",
        "/api/todos/",
    ]


@pytest.fixture
def schema_validation_config():
    """Configuration for schema validation.

    Returns settings for how strictly to validate API responses.
    """
    return {
        "validate_request": True,
        "validate_response": True,
        "validate_schema": True,
        "stateful_testing": False,
        "max_response_time_ms": 5000,
    }
