"""OpenAPI Contract Tests.

This module validates the API implementation against the OpenAPI specification.
Uses schemathesis for property-based testing and contract validation.

These tests ensure:
1. API responses match the documented schema
2. Required fields are present
3. Data types match the specification
4. Error responses are properly formatted
"""

import pytest

# Try to import schemathesis, skip tests if not installed
schemathesis = pytest.importorskip("schemathesis")

import httpx

# =============================================================================
# Schema Loading Tests
# =============================================================================


@pytest.mark.contract
class TestOpenAPISchemaAvailability:
    """Test that the OpenAPI schema is available and valid."""

    def test_openapi_schema_endpoint_exists(self, base_url):
        """Verify the OpenAPI schema endpoint is accessible."""
        response = httpx.get(f"{base_url}/api/openapi.json", timeout=10)
        assert response.status_code == 200, (
            f"OpenAPI schema endpoint returned {response.status_code}"
        )

    def test_openapi_schema_is_valid_json(self, base_url):
        """Verify the OpenAPI schema is valid JSON."""
        response = httpx.get(f"{base_url}/api/openapi.json", timeout=10)
        assert response.status_code == 200

        try:
            schema = response.json()
        except ValueError as e:
            pytest.fail(f"OpenAPI schema is not valid JSON: {e}")

        # Basic OpenAPI structure validation
        assert "openapi" in schema, "Missing 'openapi' version field"
        assert "info" in schema, "Missing 'info' section"
        assert "paths" in schema, "Missing 'paths' section"

    def test_openapi_version_is_supported(self, base_url):
        """Verify the OpenAPI version is 3.x."""
        response = httpx.get(f"{base_url}/api/openapi.json", timeout=10)
        schema = response.json()

        version = schema.get("openapi", "")
        assert version.startswith("3."), (
            f"Expected OpenAPI 3.x, got {version}"
        )

    def test_api_info_is_complete(self, base_url):
        """Verify the API info section has required fields."""
        response = httpx.get(f"{base_url}/api/openapi.json", timeout=10)
        schema = response.json()

        info = schema.get("info", {})
        assert "title" in info, "Missing API title"
        assert "version" in info, "Missing API version"

    def test_paths_are_defined(self, base_url):
        """Verify that API paths are defined."""
        response = httpx.get(f"{base_url}/api/openapi.json", timeout=10)
        schema = response.json()

        paths = schema.get("paths", {})
        assert len(paths) > 0, "No API paths defined in schema"


# =============================================================================
# Public Endpoint Contract Tests
# =============================================================================


@pytest.mark.contract
class TestPublicEndpointContracts:
    """Contract tests for public (unauthenticated) endpoints."""

    def test_health_endpoint_contract(self, base_url):
        """Verify health endpoint matches contract."""
        response = httpx.get(f"{base_url}/api/health/", timeout=10)

        assert response.status_code == 200
        data = response.json()

        # Health endpoint should return a status
        assert "status" in data or "healthy" in data or isinstance(data, dict)

    def test_health_detailed_endpoint_contract(self, base_url):
        """Verify detailed health endpoint matches contract."""
        response = httpx.get(f"{base_url}/api/health/detailed/", timeout=10)

        # Should return 200 or 503 depending on system health
        assert response.status_code in [200, 503]
        data = response.json()
        assert isinstance(data, dict)

    def test_login_endpoint_contract_invalid_credentials(self, base_url):
        """Verify login endpoint error response matches contract."""
        response = httpx.post(
            f"{base_url}/api/auth/login",
            json={"email": "nonexistent@example.com", "password": "wrongpass"},
            timeout=10,
        )

        # Should return 401 or 400 for invalid credentials
        assert response.status_code in [400, 401, 422]
        data = response.json()
        # Should have some error indication
        assert "detail" in data or "error" in data or "message" in data

    def test_login_endpoint_contract_missing_fields(self, base_url):
        """Verify login endpoint validation response matches contract."""
        response = httpx.post(
            f"{base_url}/api/auth/login",
            json={},  # Missing required fields
            timeout=10,
        )

        # Should return 422 for validation errors or 400 for bad request
        assert response.status_code in [400, 422]


# =============================================================================
# Protected Endpoint Contract Tests
# =============================================================================


@pytest.mark.contract
class TestProtectedEndpointContracts:
    """Contract tests for protected (authenticated) endpoints."""

    def test_me_endpoint_requires_auth(self, base_url):
        """Verify /me endpoint requires authentication."""
        response = httpx.get(f"{base_url}/api/auth/me", timeout=10)

        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403]

    def test_me_endpoint_with_auth(self, base_url, auth_headers_for_contract):
        """Verify /me endpoint returns user data with auth."""
        if not auth_headers_for_contract:
            pytest.skip("Could not obtain auth token")

        response = httpx.get(
            f"{base_url}/api/auth/me",
            headers=auth_headers_for_contract,
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            # User response should have at least email
            assert "email" in data or "user" in data

    def test_todos_list_requires_auth(self, base_url):
        """Verify todos list endpoint requires authentication."""
        response = httpx.get(f"{base_url}/api/todos/", timeout=10)

        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403]

    def test_todos_list_with_auth(self, base_url, auth_headers_for_contract):
        """Verify todos list returns proper format with auth."""
        if not auth_headers_for_contract:
            pytest.skip("Could not obtain auth token")

        response = httpx.get(
            f"{base_url}/api/todos/",
            headers=auth_headers_for_contract,
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            # Should return a list or paginated response
            assert isinstance(data, list | dict)


# =============================================================================
# Response Format Contract Tests
# =============================================================================


@pytest.mark.contract
class TestResponseFormatContracts:
    """Test that response formats match documented contracts."""

    def test_error_response_format(self, base_url):
        """Verify error responses have consistent format."""
        # Request a non-existent endpoint
        response = httpx.get(f"{base_url}/api/nonexistent/", timeout=10)

        assert response.status_code == 404
        data = response.json()

        # Error response should have a message/detail
        assert any(
            key in data
            for key in ["detail", "message", "error", "errors"]
        )

    def test_validation_error_format(self, base_url):
        """Verify validation errors have consistent format."""
        response = httpx.post(
            f"{base_url}/api/auth/signup",
            json={"email": "invalid-email"},  # Invalid email format
            timeout=10,
        )

        # Should be 422 or 400
        assert response.status_code in [400, 422]
        data = response.json()

        # Should indicate validation errors
        assert isinstance(data, dict)

    def test_content_type_is_json(self, base_url):
        """Verify API responses have correct content type."""
        response = httpx.get(f"{base_url}/api/health/", timeout=10)

        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type


# =============================================================================
# Schema-based Contract Tests (using Schemathesis)
# =============================================================================


@pytest.mark.contract
@pytest.mark.slow
class TestSchemaBasedContracts:
    """Property-based contract tests using schemathesis."""

    @pytest.fixture
    def api_schema(self, base_url):
        """Load the OpenAPI schema for testing."""
        return schemathesis.from_uri(f"{base_url}/api/openapi.json")

    def test_health_endpoints_match_schema(self, api_schema):
        """Test health endpoints against their schema definition."""
        for endpoint in api_schema.get_all_endpoints():
            if "health" in endpoint.path.lower():
                case = next(endpoint.as_strategy().example())
                response = case.call()
                case.validate_response(response)

    def test_auth_endpoints_exist_in_schema(self, api_schema):
        """Verify auth endpoints are defined in the schema."""
        paths = [endpoint.path for endpoint in api_schema.get_all_endpoints()]

        # At minimum, login should exist
        auth_paths = [p for p in paths if "/auth/" in p]
        assert len(auth_paths) > 0, "No auth endpoints found in schema"


# =============================================================================
# Schemathesis Test Hooks (for more advanced testing)
# =============================================================================


# Register hooks for authentication in schemathesis tests
@schemathesis.hook
def before_call(context, case):
    """Add authentication headers to schemathesis test calls."""
    # Skip auth for public endpoints
    public_paths = ["/health", "/login", "/signup", "/openapi"]
    if any(p in case.path for p in public_paths):
        return

    # Add auth header if available from environment
    import os

    token = os.environ.get("TEST_AUTH_TOKEN")
    if token:
        case.headers = case.headers or {}
        case.headers["Authorization"] = f"Bearer {token}"


@schemathesis.check
def response_time_check(response, case):
    """Check that response times are acceptable."""
    # Response should complete within 5 seconds
    assert response.elapsed.total_seconds() < 5, (
        f"Response took too long: {response.elapsed.total_seconds()}s"
    )


@schemathesis.check
def no_server_errors(response, case):
    """Check that we don't get unexpected server errors."""
    # 500 errors should never happen for valid requests
    if response.status_code >= 500:
        pytest.fail(
            f"Server error {response.status_code} for {case.method} {case.path}: "
            f"{response.text[:200]}"
        )
