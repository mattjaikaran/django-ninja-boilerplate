"""Pagination tests — prove list endpoints return the framework pagination
envelope ({count, next, previous, results}) with page/page_size controls,
user scoping, and OpenAPI documentation.
"""

import pytest
from django.test import Client

from core.tests.factories import UserFactory
from todos.tests.factories import TodoFactory


@pytest.fixture
def auth_headers(user):
    from ninja_jwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.mark.django_db
class TestPaginationEnvelope:
    def test_envelope_shape(self, auth_headers, user):
        TodoFactory.create_batch(3, user=user)
        response = Client().get("/api/todos/", **auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"count", "next", "previous", "results"}
        assert body["count"] == 3
        assert body["next"] is None
        assert body["previous"] is None
        assert isinstance(body["results"], list)

    def test_default_page_size_is_50(self, auth_headers, user):
        TodoFactory.create_batch(60, user=user)
        response = Client().get("/api/todos/", **auth_headers)
        body = response.json()
        assert body["count"] == 60
        assert len(body["results"]) == 50
        assert body["next"] is not None
        assert body["previous"] is None

    def test_page_query_param(self, auth_headers, user):
        TodoFactory.create_batch(60, user=user)
        response = Client().get("/api/todos/?page=2", **auth_headers)
        body = response.json()
        assert body["count"] == 60
        assert len(body["results"]) == 10  # second page has the remaining 10
        assert body["previous"] is not None
        assert body["next"] is None

    def test_page_size_query_param(self, auth_headers, user):
        TodoFactory.create_batch(60, user=user)
        response = Client().get("/api/todos/?page_size=10", **auth_headers)
        body = response.json()
        assert body["count"] == 60
        assert len(body["results"]) == 10

    def test_page_size_max_enforced(self, auth_headers, user):
        TodoFactory.create_batch(5, user=user)
        response = Client().get("/api/todos/?page_size=201", **auth_headers)
        assert response.status_code == 422  # 200 is the configured maximum


    def test_empty_results(self, auth_headers, user):
        response = Client().get("/api/todos/", **auth_headers)
        body = response.json()
        assert body["count"] == 0
        assert body["results"] == []
        assert body["next"] is None
        assert body["previous"] is None


@pytest.mark.django_db
class TestPaginationUserScope:
    def test_only_current_users_todos(self, auth_headers, user):
        TodoFactory.create_batch(2, user=user)
        other = UserFactory()
        TodoFactory.create_batch(3, user=other)

        response = Client().get("/api/todos/", **auth_headers)
        body = response.json()
        assert body["count"] == 2
        assert all(item["user"] == str(user.id) for item in body["results"])


@pytest.mark.django_db
class TestPaginationOpenAPI:
    def test_envelope_declared_in_schema(self):
        from api.urls import api

        schema = api.get_openapi_schema()
        response_schema = schema["paths"]["/api/todos/"]["get"]["responses"][200][
            "content"
        ]["application/json"]["schema"]
        # The framework envelope is a component ref with count/next/previous/results.
        ref = response_schema["$ref"]
        component = schema["components"]["schemas"][ref.split("/")[-1]]
        props = component["properties"]
        assert {"count", "next", "previous", "results"} <= set(props)
        assert component["required"] == ["count", "next", "previous", "results"]
