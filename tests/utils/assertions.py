"""Custom Assertions for API Response Testing.

This module provides custom assertion helpers for testing API responses.
These assertions provide clear error messages and reduce boilerplate in tests.

Usage:
    from tests.utils.assertions import assert_ok, assert_created, assert_validation_error

    def test_create_item(client):
        response = client.post("/api/items/", {"name": "Test"})
        assert_created(response)

        data = response.json()
        assert data["name"] == "Test"
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def assert_ok(response, message: str | None = None) -> None:
    """Assert that the response has a 200 OK status.

    Args:
        response: HTTP response object.
        message: Optional custom error message.
    """
    msg = message or f"Expected 200 OK, got {response.status_code}"
    if hasattr(response, "json"):
        try:
            msg = f"{msg}: {response.json()}"
        except (ValueError, AttributeError):
            pass
    assert response.status_code == 200, msg


def assert_created(response, message: str | None = None) -> None:
    """Assert that the response has a 201 Created status.

    Args:
        response: HTTP response object.
        message: Optional custom error message.
    """
    msg = message or f"Expected 201 Created, got {response.status_code}"
    if hasattr(response, "json"):
        try:
            msg = f"{msg}: {response.json()}"
        except (ValueError, AttributeError):
            pass
    assert response.status_code == 201, msg


def assert_deleted(response, message: str | None = None) -> None:
    """Assert that the response has a 204 No Content status (typical for DELETE).

    Args:
        response: HTTP response object.
        message: Optional custom error message.
    """
    msg = message or f"Expected 204 No Content, got {response.status_code}"
    assert response.status_code == 204, msg


def assert_accepted(response, message: str | None = None) -> None:
    """Assert that the response has a 202 Accepted status.

    Args:
        response: HTTP response object.
        message: Optional custom error message.
    """
    msg = message or f"Expected 202 Accepted, got {response.status_code}"
    assert response.status_code == 202, msg


def assert_not_found(response, message: str | None = None) -> None:
    """Assert that the response has a 404 Not Found status.

    Args:
        response: HTTP response object.
        message: Optional custom error message.
    """
    msg = message or f"Expected 404 Not Found, got {response.status_code}"
    assert response.status_code == 404, msg


def assert_unauthorized(response, message: str | None = None) -> None:
    """Assert that the response has a 401 Unauthorized status.

    Args:
        response: HTTP response object.
        message: Optional custom error message.
    """
    msg = message or f"Expected 401 Unauthorized, got {response.status_code}"
    assert response.status_code == 401, msg


def assert_forbidden(response, message: str | None = None) -> None:
    """Assert that the response has a 403 Forbidden status.

    Args:
        response: HTTP response object.
        message: Optional custom error message.
    """
    msg = message or f"Expected 403 Forbidden, got {response.status_code}"
    assert response.status_code == 403, msg


def assert_bad_request(response, message: str | None = None) -> None:
    """Assert that the response has a 400 Bad Request status.

    Args:
        response: HTTP response object.
        message: Optional custom error message.
    """
    msg = message or f"Expected 400 Bad Request, got {response.status_code}"
    assert response.status_code == 400, msg


def assert_validation_error(
    response,
    field: str | None = None,
    message: str | None = None,
) -> None:
    """Assert that the response has a 422 Validation Error status.

    Args:
        response: HTTP response object.
        field: Optional field name to check for in the error.
        message: Optional custom error message.
    """
    msg = message or f"Expected 422 Validation Error, got {response.status_code}"
    assert response.status_code == 422, msg

    if field:
        try:
            data = response.json()
            # Check various error formats
            errors = data.get("detail", data.get("errors", data))
            if isinstance(errors, list):
                field_in_errors = any(
                    field in str(error.get("loc", [])) or field in str(error)
                    for error in errors
                )
            elif isinstance(errors, dict):
                field_in_errors = field in errors
            else:
                field_in_errors = field in str(errors)

            assert field_in_errors, f"Expected field '{field}' in validation errors"
        except (ValueError, AttributeError, KeyError):
            pass


def assert_api_error(
    response,
    status_code: int,
    error_key: str | None = None,
    error_message: str | None = None,
) -> None:
    """Assert that the response is an API error with specific details.

    Args:
        response: HTTP response object.
        status_code: Expected HTTP status code.
        error_key: Optional error key to check for (e.g., "detail", "error").
        error_message: Optional error message substring to check for.
    """
    assert response.status_code == status_code, (
        f"Expected status {status_code}, got {response.status_code}"
    )

    if error_key or error_message:
        try:
            data = response.json()

            if error_key:
                assert error_key in data, f"Expected '{error_key}' in response"

            if error_message:
                # Check if error_message appears anywhere in the response
                response_str = str(data)
                assert error_message.lower() in response_str.lower(), (
                    f"Expected '{error_message}' in response"
                )
        except (ValueError, AttributeError):
            pass


def assert_list_response(
    response,
    min_items: int | None = None,
    max_items: int | None = None,
    item_validator: Callable | None = None,
) -> list[Any]:
    """Assert that the response is a list and optionally validate items.

    Args:
        response: HTTP response object.
        min_items: Minimum expected number of items.
        max_items: Maximum expected number of items.
        item_validator: Optional function to validate each item.

    Returns:
        list: The response data.
    """
    assert_ok(response)

    data = response.json()
    assert isinstance(data, list), f"Expected list response, got {type(data).__name__}"

    if min_items is not None:
        assert len(data) >= min_items, (
            f"Expected at least {min_items} items, got {len(data)}"
        )

    if max_items is not None:
        assert len(data) <= max_items, (
            f"Expected at most {max_items} items, got {len(data)}"
        )

    if item_validator:
        for i, item in enumerate(data):
            try:
                item_validator(item)
            except AssertionError as e:
                msg = f"Item {i} validation failed: {e}"
                raise AssertionError(msg) from e

    return data


def assert_paginated_response(
    response,
    page: int = 1,
    page_size: int | None = None,
    total_count: int | None = None,
    item_validator: Callable | None = None,
) -> dict[str, Any]:
    """Assert that the response is a paginated response.

    Args:
        response: HTTP response object.
        page: Expected page number (for verification).
        page_size: Expected page size.
        total_count: Expected total count.
        item_validator: Optional function to validate each item.

    Returns:
        dict: The response data.
    """
    assert_ok(response)

    data = response.json()
    assert isinstance(data, dict), (
        f"Expected dict response for pagination, got {type(data).__name__}"
    )

    # Check for common pagination fields
    items_key = None
    for key in ["results", "items", "data"]:
        if key in data:
            items_key = key
            break

    if items_key is None:
        # Might be a simple list with metadata in headers
        if "count" in data or "total" in data:
            pass  # Has pagination metadata
        else:
            msg = "Expected paginated response with 'results', 'items', or 'data' key"
            raise AssertionError(msg)

    if items_key:
        items = data[items_key]
        assert isinstance(items, list), f"Expected list for '{items_key}'"

        if page_size is not None:
            assert len(items) <= page_size, (
                f"Expected at most {page_size} items per page"
            )

        if item_validator:
            for i, item in enumerate(items):
                try:
                    item_validator(item)
                except AssertionError as e:
                    msg = f"Item {i} validation failed: {e}"
                    raise AssertionError(msg) from e

    if total_count is not None:
        actual_count = data.get("count") or data.get("total") or data.get("total_count")
        assert actual_count == total_count, (
            f"Expected total count {total_count}, got {actual_count}"
        )

    return data


def assert_response_contains(
    response,
    fields: list[str],
    message: str | None = None,
) -> dict[str, Any]:
    """Assert that the response contains specific fields.

    Args:
        response: HTTP response object.
        fields: List of field names that must be present.
        message: Optional custom error message.

    Returns:
        dict: The response data.
    """
    assert_ok(response)

    data = response.json()

    for field in fields:
        assert field in data, message or f"Expected field '{field}' in response"

    return data


def assert_response_matches(
    response,
    expected: dict[str, Any],
    message: str | None = None,
) -> dict[str, Any]:
    """Assert that the response matches expected values.

    Args:
        response: HTTP response object.
        expected: Dictionary of expected field values.
        message: Optional custom error message.

    Returns:
        dict: The response data.
    """
    assert_ok(response)

    data = response.json()

    for key, expected_value in expected.items():
        actual_value = data.get(key)
        assert actual_value == expected_value, (
            message
            or f"Field '{key}': expected {expected_value!r}, got {actual_value!r}"
        )

    return data


def assert_status(
    response,
    status_code: int | list[int],
    message: str | None = None,
) -> None:
    """Assert that the response has one of the expected status codes.

    Args:
        response: HTTP response object.
        status_code: Expected status code or list of acceptable codes.
        message: Optional custom error message.
    """
    if isinstance(status_code, int):
        status_code = [status_code]

    msg = message or (f"Expected status {status_code}, got {response.status_code}")

    if hasattr(response, "json"):
        try:
            msg = f"{msg}: {response.json()}"
        except (ValueError, AttributeError):
            pass

    assert response.status_code in status_code, msg
