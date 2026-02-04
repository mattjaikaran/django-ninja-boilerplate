"""Feature Flag Middleware.

This module provides middleware for adding feature flags to the request context.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.http import HttpRequest, HttpResponse

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class FeatureFlagMiddleware:
    """Middleware that adds feature flags to the request context.

    This middleware:
    - Attaches a feature_flags object to the request
    - Provides easy access to flag checks within views
    - Caches flag status for the duration of the request

    Usage in views:
        def my_view(request):
            if request.feature_flags.is_enabled("new_feature"):
                # New feature logic
                pass

            variant = request.feature_flags.get_variant("checkout_ab_test")
            # Use variant for A/B testing

    Add to MIDDLEWARE in settings:
        MIDDLEWARE = [
            ...
            'core.features.middleware.FeatureFlagMiddleware',
        ]
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and add feature flags context.

        Args:
            request: The incoming HTTP request

        Returns:
            The HTTP response
        """
        # Attach feature flags helper to request
        request.feature_flags = RequestFeatureFlags(request)

        response = self.get_response(request)

        return response


class RequestFeatureFlags:
    """Helper class for accessing feature flags within a request.

    Provides convenient methods for checking flags and getting variants,
    with request-level caching for performance.
    """

    def __init__(self, request: HttpRequest):
        """Initialize the helper with the request.

        Args:
            request: The HTTP request object
        """
        self.request = request
        self._cache: dict[str, bool | str] = {}
        self._all_flags: dict[str, bool | str] | None = None

    @property
    def user(self):
        """Get the user from the request if authenticated."""
        if hasattr(self.request, "user") and self.request.user.is_authenticated:
            return self.request.user
        return None

    def is_enabled(
        self,
        flag_name: str,
        default: bool = False,
        context: dict | None = None,
    ) -> bool:
        """Check if a feature flag is enabled.

        Args:
            flag_name: The name of the feature flag
            default: Default value if flag doesn't exist
            context: Additional context for condition evaluation

        Returns:
            True if the flag is enabled, False otherwise
        """
        cache_key = f"enabled:{flag_name}"

        if cache_key not in self._cache:
            from .service import feature_flag_service

            self._cache[cache_key] = feature_flag_service.is_enabled(
                flag_name,
                user=self.user,
                default=default,
                context=context,
            )

        return self._cache[cache_key]

    def get_variant(self, flag_name: str, default: str = "control") -> str:
        """Get the A/B test variant for the current user.

        Args:
            flag_name: The name of the A/B test feature flag
            default: Default variant if flag doesn't exist

        Returns:
            The variant name for the current user
        """
        cache_key = f"variant:{flag_name}"

        if cache_key not in self._cache:
            from .service import feature_flag_service

            self._cache[cache_key] = feature_flag_service.get_variant(
                flag_name,
                user=self.user,
                default=default,
            )

        return self._cache[cache_key]

    def get_all_flags(self) -> dict[str, bool | str]:
        """Get all feature flags for the current user.

        Returns:
            Dictionary mapping flag names to their status or variant
        """
        if self._all_flags is None:
            from .service import feature_flag_service

            if self.user:
                self._all_flags = feature_flag_service.get_flags_for_user(self.user)
            else:
                # For anonymous users, just return enabled boolean flags
                flags = feature_flag_service.get_all_flags(enabled_only=True)
                self._all_flags = {
                    flag.name: feature_flag_service.is_enabled(flag.name)
                    for flag in flags
                }

        return self._all_flags

    def __contains__(self, flag_name: str) -> bool:
        """Check if a flag exists and is enabled.

        Allows: if "flag_name" in request.feature_flags
        """
        return self.is_enabled(flag_name)

    def __getitem__(self, flag_name: str) -> bool:
        """Get flag status using bracket notation.

        Allows: request.feature_flags["flag_name"]
        """
        return self.is_enabled(flag_name)
