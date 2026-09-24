"""Exception handling tests — prove domain exceptions map to their declared
statuses and unexpected errors return safe JSON 500 (no exception leakage).

These are isolated handler tests: they import the handlers from
``api.exceptions`` directly and exercise them with a plain HttpRequest, so they
do not depend on the full application import graph.
"""

import json

import pytest
from django.http import HttpRequest

from api.exceptions import (
    APIPermissionError,
    AuthenticationError,
    BaseAPIException,
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    handle_api_exception,
    handle_generic_exception,
)


def make_request() -> HttpRequest:
    request = HttpRequest()
    request.META = {"X-Request-ID": "test-request-id"}
    return request


def _body(response) -> dict:
    return json.loads(response.content.decode())


class TestDomainExceptionMapping:
    """Every BaseAPIException subclass maps to its declared status code."""

    @pytest.mark.parametrize(
        ("exc_cls", "status"),
        [
            (ValidationError, 400),
            (AuthenticationError, 401),
            (APIPermissionError, 403),
            (NotFoundError, 404),
            (ConflictError, 409),
            (RateLimitError, 429),
            (ExternalServiceError, 502),
        ],
    )
    def test_status_and_shape(self, exc_cls, status):
        exc = exc_cls("boom")
        assert exc.status_code == status
        assert issubclass(exc_cls, BaseAPIException)

        response = handle_api_exception(make_request(), exc)
        assert response.status_code == status
        body = _body(response)
        assert body["error"] is True
        assert body["message"] == "boom"
        assert body["code"] == exc_cls.default_code


class TestSafe500:
    def test_unexpected_exception_returns_safe_json(self):
        response = handle_generic_exception(make_request(), ValueError("secret detail"))
        assert response.status_code == 500
        body = _body(response)
        assert body == {
            "error": True,
            "message": "An internal error occurred",
            "code": "internal_error",
        }
        # The raw exception text must not leak into the response body.
        assert "secret detail" not in response.content.decode()
