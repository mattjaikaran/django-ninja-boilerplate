"""In-process OpenAPI contract tests for registered routes."""

import pytest
from django.test import Client

from api.urls import api


@pytest.mark.django_db
class TestOpenAPIContract:
    def test_schema_endpoint_matches_registered_api(self):
        response = Client().get("/api/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["openapi"].startswith("3.")
        assert "/api/auth/logout" in schema["paths"]
        assert "/api/users/" in schema["paths"]
        assert schema["paths"]["/api/auth/logout"]["post"]["security"]

    @pytest.mark.parametrize(
        ("path", "method", "requires_auth"),
        [
            ("/api/auth/login", "post", False),
            ("/api/token/refresh", "post", False),
            ("/api/auth/logout", "post", True),
            ("/api/auth/me", "get", True),
            ("/api/users/", "get", True),
            ("/api/audit/", "get", True),
            ("/api/decisions/evaluate", "post", True),
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
