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
    """Routes reachable without credentials, as ``{"method", "path"}`` specs.

    Deployment probes (liveness/readiness/basic health) stay public so
    orchestrators can reach them with plain GET requests. Auth operations and
    token issuance are public because they run before a token exists.
    """
    return [
        # Deployment probes — no credentials, no internal detail.
        {"method": "GET", "path": "/api/health/"},
        {"method": "GET", "path": "/api/health/liveness"},
        {"method": "GET", "path": "/api/health/readiness"},
        # Authentication operations — reachable before a token exists.
        {"method": "POST", "path": "/api/auth/login"},
        {"method": "POST", "path": "/api/auth/login/username"},
        {"method": "POST", "path": "/api/auth/signup"},
        {"method": "POST", "path": "/api/auth/passwordless/login/request"},
        {"method": "POST", "path": "/api/auth/passwordless/login/verify"},
        {"method": "POST", "path": "/api/auth/otp/request"},
        # JWT issuance/refresh — the endpoints that mint tokens.
        {"method": "POST", "path": "/api/token/pair"},
        {"method": "POST", "path": "/api/token/refresh"},
    ]


@pytest.fixture(scope="session")
def protected_endpoints():
    """Routes that require a JWT, as ``{"method", "path"}`` specs.

    These are network-private: observability detail/metrics, auth
    profile/status/logout, user administration, task internals, audit logs,
    decisions, API-key management and todo data. Several additionally require
    a staff account (checked by the controller's permission classes).
    """
    return [
        # Network-private observability (staff only).
        {"method": "GET", "path": "/api/health/detailed"},
        {"method": "GET", "path": "/api/health/component/database"},
        {"method": "GET", "path": "/api/health/system"},
        {"method": "GET", "path": "/api/metrics"},
        # Authenticated session/profile.
        {"method": "GET", "path": "/api/auth/me"},
        {"method": "GET", "path": "/api/auth/status"},
        {"method": "POST", "path": "/api/auth/logout"},
        # Administration and data.
        {"method": "GET", "path": "/api/users/"},
        {"method": "GET", "path": "/api/tasks/stats"},
        {"method": "GET", "path": "/api/tasks/scheduler/"},
        {"method": "GET", "path": "/api/tasks/dlq/"},
        {"method": "GET", "path": "/api/audit/"},
        {"method": "POST", "path": "/api/decisions/evaluate"},
        {"method": "GET", "path": "/api/api-keys/"},
        {"method": "GET", "path": "/api/todos/"},
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
