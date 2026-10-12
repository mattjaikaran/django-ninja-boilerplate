"""Pagination tests: prove the todo list returns the framework pagination
envelope ({count, next, previous, results}) with page/page_size controls.
"""

import pytest
from django.test import Client

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
