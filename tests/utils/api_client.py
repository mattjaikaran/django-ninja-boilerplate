"""Enhanced Test API Client with Authentication Helpers.

This module provides an enhanced API client for testing Django Ninja APIs.
It simplifies authentication and provides a consistent interface for API calls.

Usage:
    from tests.utils.api_client import APITestClient, AuthenticatedAPIClient

    # Anonymous client
    client = APITestClient()
    response = client.get("/api/health/")

    # Authenticated client
    auth_client = AuthenticatedAPIClient()
    auth_client.login("user@example.com", "password")
    response = auth_client.get("/api/auth/me")
"""

from __future__ import annotations

import json
from typing import Any

from django.test import Client


class APITestClient:
    """Enhanced test client for API testing.

    Provides a convenient interface for making API requests with proper
    headers and JSON handling.
    """

    def __init__(self, client: Client | None = None):
        """Initialize the API test client.

        Args:
            client: Optional Django test client. Creates new one if not provided.
        """
        self.client = client or Client()
        self.default_headers = {
            "HTTP_ACCEPT": "application/json",
        }
        self.auth_token: str | None = None
        self.last_response = None

    def _get_headers(self, extra_headers: dict | None = None) -> dict:
        """Build request headers.

        Args:
            extra_headers: Additional headers to include.

        Returns:
            dict: Combined headers for the request.
        """
        headers = self.default_headers.copy()

        if self.auth_token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {self.auth_token}"

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def get(
        self,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
    ):
        """Make a GET request.

        Args:
            path: URL path to request.
            params: Optional query parameters.
            headers: Optional additional headers.

        Returns:
            HttpResponse: The response object.
        """
        self.last_response = self.client.get(
            path,
            data=params,
            **self._get_headers(headers),
        )
        return self.last_response

    def post(
        self,
        path: str,
        data: dict | None = None,
        headers: dict | None = None,
        content_type: str = "application/json",
    ):
        """Make a POST request.

        Args:
            path: URL path to request.
            data: Request body data.
            headers: Optional additional headers.
            content_type: Content type for the request.

        Returns:
            HttpResponse: The response object.
        """
        self.last_response = self.client.post(
            path,
            data=json.dumps(data) if data else None,
            content_type=content_type,
            **self._get_headers(headers),
        )
        return self.last_response

    def put(
        self,
        path: str,
        data: dict | None = None,
        headers: dict | None = None,
        content_type: str = "application/json",
    ):
        """Make a PUT request.

        Args:
            path: URL path to request.
            data: Request body data.
            headers: Optional additional headers.
            content_type: Content type for the request.

        Returns:
            HttpResponse: The response object.
        """
        self.last_response = self.client.put(
            path,
            data=json.dumps(data) if data else None,
            content_type=content_type,
            **self._get_headers(headers),
        )
        return self.last_response

    def patch(
        self,
        path: str,
        data: dict | None = None,
        headers: dict | None = None,
        content_type: str = "application/json",
    ):
        """Make a PATCH request.

        Args:
            path: URL path to request.
            data: Request body data.
            headers: Optional additional headers.
            content_type: Content type for the request.

        Returns:
            HttpResponse: The response object.
        """
        self.last_response = self.client.patch(
            path,
            data=json.dumps(data) if data else None,
            content_type=content_type,
            **self._get_headers(headers),
        )
        return self.last_response

    def delete(
        self,
        path: str,
        headers: dict | None = None,
    ):
        """Make a DELETE request.

        Args:
            path: URL path to request.
            headers: Optional additional headers.

        Returns:
            HttpResponse: The response object.
        """
        self.last_response = self.client.delete(
            path,
            **self._get_headers(headers),
        )
        return self.last_response

    def json(self) -> dict[str, Any]:
        """Get the JSON response from the last request.

        Returns:
            dict: Parsed JSON response.

        Raises:
            ValueError: If no request has been made or response is not JSON.
        """
        if self.last_response is None:
            msg = "No request has been made"
            raise ValueError(msg)

        return self.last_response.json()

    def status_code(self) -> int:
        """Get the status code from the last request.

        Returns:
            int: HTTP status code.

        Raises:
            ValueError: If no request has been made.
        """
        if self.last_response is None:
            msg = "No request has been made"
            raise ValueError(msg)

        return self.last_response.status_code


class AuthenticatedAPIClient(APITestClient):
    """API client with authentication support.

    Provides methods for logging in and managing authentication tokens.
    """

    def __init__(self, client: Client | None = None):
        """Initialize the authenticated API client."""
        super().__init__(client)
        self.user = None
        self.refresh_token: str | None = None

    def login(
        self,
        email: str,
        password: str,
        login_endpoint: str = "/api/auth/login",
    ) -> bool:
        """Log in with email and password.

        Args:
            email: User email.
            password: User password.
            login_endpoint: Optional custom login endpoint.

        Returns:
            bool: True if login was successful.
        """
        response = self.post(
            login_endpoint,
            data={"email": email, "password": password},
        )

        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get("access") or data.get("token")
            self.refresh_token = data.get("refresh")
            self.user = data.get("user")
            return True

        return False

    def login_with_token(self, token: str) -> None:
        """Set the authentication token directly.

        Args:
            token: JWT access token.
        """
        self.auth_token = token

    def logout(self, logout_endpoint: str = "/api/auth/logout") -> bool:
        """Log out the current user.

        Args:
            logout_endpoint: Optional custom logout endpoint.

        Returns:
            bool: True if logout was successful.
        """
        if not self.auth_token:
            return True

        response = self.post(logout_endpoint)
        success = response.status_code in [200, 204]

        if success:
            self.auth_token = None
            self.refresh_token = None
            self.user = None

        return success

    def refresh_auth(self, refresh_endpoint: str = "/api/auth/refresh") -> bool:
        """Refresh the authentication token.

        Args:
            refresh_endpoint: Optional custom refresh endpoint.

        Returns:
            bool: True if refresh was successful.
        """
        if not self.refresh_token:
            return False

        # Temporarily clear auth token for refresh request
        old_token = self.auth_token
        self.auth_token = None

        response = self.post(
            refresh_endpoint,
            data={"refresh": self.refresh_token},
        )

        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get("access") or data.get("token")
            return True

        # Restore old token if refresh failed
        self.auth_token = old_token
        return False

    def signup(
        self,
        email: str,
        password: str,
        first_name: str = "Test",
        last_name: str = "User",
        signup_endpoint: str = "/api/auth/signup",
        auto_login: bool = True,
    ) -> bool:
        """Create a new user account.

        Args:
            email: User email.
            password: User password.
            first_name: User first name.
            last_name: User last name.
            signup_endpoint: Optional custom signup endpoint.
            auto_login: Whether to automatically log in after signup.

        Returns:
            bool: True if signup was successful.
        """
        response = self.post(
            signup_endpoint,
            data={
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        if response.status_code in [200, 201]:
            if auto_login:
                return self.login(email, password)
            return True

        return False

    def signup_and_login(
        self,
        email: str,
        password: str,
        first_name: str = "Test",
        last_name: str = "User",
    ) -> bool:
        """Signup and login in one step.

        Args:
            email: User email.
            password: User password.
            first_name: User first name.
            last_name: User last name.

        Returns:
            bool: True if signup and login were successful.
        """
        return self.signup(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            auto_login=True,
        )

    def get_current_user(self, me_endpoint: str = "/api/auth/me") -> dict | None:
        """Get the current authenticated user's profile.

        Args:
            me_endpoint: Optional custom profile endpoint.

        Returns:
            dict: User profile data or None if not authenticated.
        """
        if not self.auth_token:
            return None

        response = self.get(me_endpoint)
        if response.status_code == 200:
            return response.json()

        return None

    @classmethod
    def create_authenticated(
        cls,
        user,
        client: Client | None = None,
    ) -> AuthenticatedAPIClient:
        """Create an authenticated client for a user.

        This is useful when you have a user instance from a factory
        and want to create an authenticated client directly.

        Args:
            user: User instance.
            client: Optional Django test client.

        Returns:
            AuthenticatedAPIClient: Authenticated client instance.
        """
        api_client = cls(client)

        # Generate token for user
        try:
            from ninja_jwt.tokens import RefreshToken
        except ImportError:
            from django_ninja_jwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        api_client.auth_token = str(refresh.access_token)
        api_client.refresh_token = str(refresh)
        api_client.user = user

        return api_client
