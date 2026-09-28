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
    orchestrators can reach them with plain GET requests. Auth operations,
    OTP flows, token issuance/refresh, and Centrifugo real-time token minting
    are public because they run before a JWT exists.

    Paths use the exact OpenAPI path templates (``{param}`` placeholders
    included) so they can be compared against the generated schema.
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
        # OTP flows — request/verify codes without a JWT.
        {"method": "POST", "path": "/api/auth/otp/request"},
        {"method": "POST", "path": "/api/auth/otp/resend"},
        {"method": "POST", "path": "/api/auth/otp/verify"},
        {"method": "POST", "path": "/api/auth/otp/verify-token"},
        {"method": "POST", "path": "/api/auth/otp/email/verify"},
        {"method": "POST", "path": "/api/auth/otp/password-reset/request"},
        {"method": "POST", "path": "/api/auth/otp/password-reset/confirm"},
        # Real-time token minting — authenticated via token request, not JWT.
        {"method": "POST", "path": "/api/realtime/connection-token"},
        {"method": "POST", "path": "/api/realtime/subscription-token"},
        # JWT issuance/refresh/verify — the endpoints that mint tokens.
        {"method": "POST", "path": "/api/token/pair"},
        {"method": "POST", "path": "/api/token/refresh"},
        {"method": "POST", "path": "/api/token/verify"},
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
        {"method": "GET", "path": "/api/health/component/{component}"},
        {"method": "GET", "path": "/api/health/system"},
        # Authenticated session/profile.
        {"method": "GET", "path": "/api/auth/me"},
        {"method": "GET", "path": "/api/auth/status"},
        {"method": "POST", "path": "/api/auth/logout"},
        # Two-factor operations require JWT authentication.
        {"method": "POST", "path": "/api/auth/otp/2fa/request"},
        {"method": "POST", "path": "/api/auth/otp/2fa/verify"},
        # User administration.
        {"method": "GET", "path": "/api/users/"},
        {"method": "GET", "path": "/api/users/active"},
        {"method": "GET", "path": "/api/users/staff"},
        {"method": "POST", "path": "/api/users/superuser"},
        {"method": "GET", "path": "/api/users/{user_id}"},
        {"method": "PUT", "path": "/api/users/{user_id}"},
        {"method": "DELETE", "path": "/api/users/{user_id}"},
        # API-key management.
        {"method": "GET", "path": "/api/api-keys/"},
        {"method": "POST", "path": "/api/api-keys/"},
        {"method": "DELETE", "path": "/api/api-keys/{key_id}"},
        {"method": "POST", "path": "/api/api-keys/{key_id}/rotate"},
        # Audit logs (staff only).
        {"method": "GET", "path": "/api/audit/"},
        {"method": "GET", "path": "/api/audit/actions"},
        {"method": "GET", "path": "/api/audit/failed-logins"},
        {"method": "GET", "path": "/api/audit/models"},
        {"method": "GET", "path": "/api/audit/stats/summary"},
        {"method": "GET", "path": "/api/audit/ip/{ip_address}"},
        {"method": "GET", "path": "/api/audit/user/{user_email}"},
        {"method": "GET", "path": "/api/audit/object/{model_name}/{object_id}"},
        {"method": "GET", "path": "/api/audit/{audit_log_id}"},
        # Task status/progress.
        {"method": "GET", "path": "/api/tasks/stats"},
        {"method": "GET", "path": "/api/tasks/recent"},
        {"method": "GET", "path": "/api/tasks/active"},
        {"method": "POST", "path": "/api/tasks/cleanup"},
        {"method": "GET", "path": "/api/tasks/{task_id}/status"},
        {"method": "GET", "path": "/api/tasks/{task_id}/progress"},
        {"method": "POST", "path": "/api/tasks/{task_id}/revoke"},
        # Periodic task scheduler.
        {"method": "GET", "path": "/api/tasks/scheduler/"},
        {"method": "GET", "path": "/api/tasks/scheduler/stats"},
        {"method": "POST", "path": "/api/tasks/scheduler/crontab"},
        {"method": "POST", "path": "/api/tasks/scheduler/interval"},
        {"method": "GET", "path": "/api/tasks/scheduler/{task_id}"},
        {"method": "PUT", "path": "/api/tasks/scheduler/{task_id}"},
        {"method": "DELETE", "path": "/api/tasks/scheduler/{task_id}"},
        {"method": "POST", "path": "/api/tasks/scheduler/{task_id}/run"},
        {"method": "POST", "path": "/api/tasks/scheduler/{task_id}/toggle"},
        # Dead-letter queue.
        {"method": "GET", "path": "/api/tasks/dlq/"},
        {"method": "GET", "path": "/api/tasks/dlq/stats"},
        {"method": "POST", "path": "/api/tasks/dlq/cleanup"},
        {"method": "POST", "path": "/api/tasks/dlq/resolve-bulk"},
        {"method": "POST", "path": "/api/tasks/dlq/retry-all"},
        {"method": "GET", "path": "/api/tasks/dlq/{entry_id}"},
        {"method": "DELETE", "path": "/api/tasks/dlq/{entry_id}"},
        {"method": "POST", "path": "/api/tasks/dlq/{entry_id}/resolve"},
        {"method": "POST", "path": "/api/tasks/dlq/{entry_id}/retry"},
        # Decisions.
        {"method": "POST", "path": "/api/decisions/evaluate"},
        # Todo data — four controllers expose the same CRUD + search surface.
        {"method": "GET", "path": "/api/todos/"},
        {"method": "POST", "path": "/api/todos/"},
        {"method": "GET", "path": "/api/todos/completed"},
        {"method": "GET", "path": "/api/todos/pending"},
        {"method": "GET", "path": "/api/todos/search"},
        {"method": "GET", "path": "/api/todos/{todo_id}"},
        {"method": "PUT", "path": "/api/todos/{todo_id}"},
        {"method": "DELETE", "path": "/api/todos/{todo_id}"},
        {"method": "GET", "path": "/api/todos-basic/"},
        {"method": "POST", "path": "/api/todos-basic/"},
        {"method": "GET", "path": "/api/todos-basic/completed"},
        {"method": "GET", "path": "/api/todos-basic/pending"},
        {"method": "GET", "path": "/api/todos-basic/search"},
        {"method": "GET", "path": "/api/todos-basic/{todo_id}"},
        {"method": "PUT", "path": "/api/todos-basic/{todo_id}"},
        {"method": "DELETE", "path": "/api/todos-basic/{todo_id}"},
        {"method": "GET", "path": "/api/todos-declarative/"},
        {"method": "POST", "path": "/api/todos-declarative/"},
        {"method": "GET", "path": "/api/todos-declarative/completed"},
        {"method": "GET", "path": "/api/todos-declarative/pending"},
        {"method": "GET", "path": "/api/todos-declarative/search"},
        {"method": "GET", "path": "/api/todos-declarative/{todo_id}"},
        {"method": "PUT", "path": "/api/todos-declarative/{todo_id}"},
        {"method": "DELETE", "path": "/api/todos-declarative/{todo_id}"},
        {"method": "GET", "path": "/api/todos-partial/"},
        {"method": "POST", "path": "/api/todos-partial/"},
        {"method": "GET", "path": "/api/todos-partial/completed"},
        {"method": "GET", "path": "/api/todos-partial/pending"},
        {"method": "GET", "path": "/api/todos-partial/search"},
        {"method": "GET", "path": "/api/todos-partial/{todo_id}"},
        {"method": "PUT", "path": "/api/todos-partial/{todo_id}"},
        {"method": "DELETE", "path": "/api/todos-partial/{todo_id}"},
        # Schema-hidden protected routes (see ``schema_hidden_endpoints``).
        {"method": "GET", "path": "/api/metrics"},
        {"method": "GET", "path": "/api/events/stream/"},
    ]


@pytest.fixture(scope="session")
def schema_hidden_endpoints():
    """Protected routes that ``api.get_openapi_schema()`` omits.

    These are a *subset* of ``protected_endpoints``, listed separately only so
    the exhaustiveness test can reconstruct the full registered-route set
    (OpenAPI operations plus the routes hidden from the schema). They are not
    a third classification: ``include_in_schema=False`` hides ``/api/metrics``
    from the docs, and the SSE streaming endpoint is a raw Django view mounted
    outside the Ninja router (JWT via query string).
    """
    return [
        {"method": "GET", "path": "/api/metrics"},
        {"method": "GET", "path": "/api/events/stream/"},
    ]


@pytest.fixture(scope="session")
def route_exclusions():
    """Docs/schema URLs that are not API operations, as method/path specs.

    These are framework endpoints (Swagger UI and the OpenAPI JSON) mounted on
    the same ``/api/`` prefix. They are intentionally excluded from the
    public/protected classification because they expose no business API.
    """
    return [
        {"method": "GET", "path": "/api/docs"},
        {"method": "GET", "path": "/api/docs/"},
        {"method": "GET", "path": "/api/openapi.json"},
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
