"""Testing utilities for Django Ninja Boilerplate.

This package provides common testing utilities including:
- api_client: Enhanced test API client with auth helpers
- assertions: Custom assertions for API responses
- factories: Base factory utilities
"""

from tests.utils.api_client import APITestClient, AuthenticatedAPIClient
from tests.utils.assertions import (
    assert_api_error,
    assert_created,
    assert_deleted,
    assert_forbidden,
    assert_list_response,
    assert_not_found,
    assert_ok,
    assert_paginated_response,
    assert_unauthorized,
    assert_validation_error,
)
from tests.utils.factories import BaseTestFactory, TestDataGenerator

__all__ = [
    # API Client
    "APITestClient",
    "AuthenticatedAPIClient",
    # Assertions
    "assert_ok",
    "assert_created",
    "assert_deleted",
    "assert_not_found",
    "assert_unauthorized",
    "assert_forbidden",
    "assert_validation_error",
    "assert_api_error",
    "assert_list_response",
    "assert_paginated_response",
    # Factories
    "BaseTestFactory",
    "TestDataGenerator",
]
