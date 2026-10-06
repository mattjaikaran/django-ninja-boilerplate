"""In-process OpenAPI contract tests for registered routes."""

import pytest
from django.test import Client

from api.urls import api

#: Components owned by third-party packages, not by CamelCaseSchema.
#: ``DynamicInput`` is ninja-extra's pagination query input (``page_size``).
THIRD_PARTY_COMPONENTS = {"DynamicInput"}


@pytest.mark.django_db
class TestOpenAPIContract:
    def test_schema_endpoint_matches_registered_api(self):
        response = Client().get("/api/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["openapi"].startswith("3.")
        assert "/api/auth/me" in schema["paths"]
        assert "/api/users/" in schema["paths"]
        assert schema["paths"]["/api/auth/me"]["get"]["security"]

    @pytest.mark.parametrize(
        ("path", "method", "requires_auth"),
        [
            ("/api/auth/login", "post", False),
            ("/api/token/refresh", "post", False),
            ("/api/auth/logout", "post", False),
            ("/api/auth/me", "get", True),
            ("/api/users/", "get", True),
            ("/api/audit/", "get", True),
        ],
    )
    def test_openapi_declares_route_auth(self, path, method, requires_auth):
        operation = api.get_openapi_schema()["paths"][path][method]
        assert bool(operation.get("security")) is requires_auth

    @pytest.mark.parametrize("path", ["/api/users/", "/api/audit/", "/api/todos/"])
    def test_openapi_declares_page_envelope(self, path):
        schema = api.get_openapi_schema()
        response = schema["paths"][path]["get"]["responses"][200]
        ref = response["content"]["application/json"]["schema"]["$ref"]
        properties = schema["components"]["schemas"][ref.split("/")[-1]]["properties"]
        assert {"count", "next", "previous", "results"} <= properties.keys()

    def test_versioned_paths_are_absent(self):
        paths = api.get_openapi_schema()["paths"]
        assert all(not path.startswith(("/api/v1/", "/api/v2/")) for path in paths)

    def test_component_properties_use_camel_case_aliases(self):
        """CamelCaseSchema aliases must reach the exported contract.

        The frontend generates Zod from this schema, so a snake_case property
        here means the generated client and the runtime JSON disagree.
        """
        schemas = api.get_openapi_schema()["components"]["schemas"]
        leaks = sorted(
            f"{name}.{prop}"
            for name, component in schemas.items()
            if name not in THIRD_PARTY_COMPONENTS
            for prop in component.get("properties", {})
            if "_" in prop
        )
        assert not leaks, f"snake_case properties in OpenAPI: {leaks}"
