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
        assert (
            schema["components"]["securitySchemes"]["CookieJWTAuth"]["in"] == "cookie"
        )

    @pytest.mark.parametrize(
        ("path", "method", "requires_auth"),
        [
            ("/api/auth/login", "post", False),
            ("/api/auth/refresh", "post", True),
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

    def test_cookie_authentication_response_contract(self):
        schema = api.get_openapi_schema()
        user = schema["components"]["schemas"]["UserSchema"]["properties"]
        assert {"firstName", "isActive", "dateJoined"} <= user.keys()
        assert (
            "csrfToken"
            in schema["components"]["schemas"]["CSRFResponseSchema"]["properties"]
        )
        for path in ("/api/auth/refresh", "/api/auth/logout"):
            operation = schema["paths"][path]["post"]
            assert "requestBody" not in operation
            assert not operation.get("parameters")
        assert not any(path.startswith("/api/token/") for path in schema["paths"])

    def test_operation_ids_are_unique_and_deterministic(self):
        from collections import Counter

        schema = api.get_openapi_schema()
        ids = [
            operation["operationId"]
            for operations in schema["paths"].values()
            for operation in operations.values()
        ]
        assert all(count == 1 for count in Counter(ids).values())
        assert schema["paths"]["/api/auth/login"]["post"]["operationId"] == "auth_login"
        assert schema["paths"]["/api/todos/"]["get"]["operationId"] == "todo_list_todos"
