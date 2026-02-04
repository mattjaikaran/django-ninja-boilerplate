"""Feature Flag Decorators.

This module provides decorators for controlling access to views
based on feature flag status.
"""

from __future__ import annotations

import functools
import logging
import types
from typing import TYPE_CHECKING, Any, Self

from django.http import JsonResponse

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def feature_flag(
    flag_name: str,
    default: bool = False,
    redirect_response: dict[str, Any] | None = None,
    pass_flag_status: bool = False,
):
    """Decorator to control access to a view based on feature flag status.

    If the flag is disabled, returns a 404 or custom response.
    Can optionally pass the flag status to the view.

    Usage:
        @api_controller("/new-feature", tags=["New Feature"])
        class NewFeatureController:
            @http_get("/")
            @feature_flag("new_feature_enabled")
            def get_new_feature(self, request):
                return {"message": "New feature is available!"}

            @http_get("/with-status")
            @feature_flag("partial_rollout", pass_flag_status=True)
            def get_with_status(self, request, feature_enabled: bool):
                if feature_enabled:
                    return {"mode": "new"}
                return {"mode": "legacy"}

    Args:
        flag_name: The name of the feature flag to check
        default: Default value if flag doesn't exist
        redirect_response: Custom response when flag is disabled
        pass_flag_status: Whether to pass flag status as kwarg to view
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            from .service import feature_flag_service

            # Extract request from args or kwargs
            request = None
            user = None

            # Check if first arg is the request
            if args and hasattr(args[0], "user"):
                request = args[0]
            elif "request" in kwargs:
                request = kwargs["request"]

            # Get user from request if available
            if request and hasattr(request, "user") and request.user.is_authenticated:
                user = request.user

            # Check feature flag
            is_enabled = feature_flag_service.is_enabled(
                flag_name,
                user=user,
                default=default,
            )

            # If passing flag status, add it to kwargs
            if pass_flag_status:
                kwargs["feature_enabled"] = is_enabled
                return func(self, *args, **kwargs)

            # If flag is disabled and we're not passing status
            if not is_enabled:
                logger.debug(
                    "Feature flag '%s' is disabled for user %s",
                    flag_name,
                    user.pk if user else "anonymous",
                )

                if redirect_response:
                    return JsonResponse(redirect_response, status=404)

                return JsonResponse(
                    {
                        "error": "Feature not available",
                        "message": f"The feature '{flag_name}' is not currently available",
                        "code": "feature_disabled",
                    },
                    status=404,
                )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def require_feature(
    flag_name: str,
    error_message: str | None = None,
):
    """Decorator that requires a feature flag to be enabled.

    Similar to feature_flag but specifically designed for required features.
    Returns a 403 Forbidden if the flag is disabled.

    Usage:
        @http_post("/beta-action")
        @require_feature("beta_access", error_message="Beta access required")
        def beta_action(self, request):
            return {"status": "beta action completed"}

    Args:
        flag_name: The name of the feature flag to require
        error_message: Custom error message when flag is disabled
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            from .service import feature_flag_service

            # Extract request from args or kwargs
            request = None
            user = None

            if args and hasattr(args[0], "user"):
                request = args[0]
            elif "request" in kwargs:
                request = kwargs["request"]

            if request and hasattr(request, "user") and request.user.is_authenticated:
                user = request.user

            # Check feature flag
            is_enabled = feature_flag_service.is_enabled(
                flag_name,
                user=user,
                default=False,
            )

            if not is_enabled:
                message = (
                    error_message
                    or f"Feature '{flag_name}' is required but not enabled"
                )
                logger.warning(
                    "Access denied: feature '%s' required but disabled for user %s",
                    flag_name,
                    user.pk if user else "anonymous",
                )

                return JsonResponse(
                    {
                        "error": "Feature required",
                        "message": message,
                        "code": "feature_required",
                    },
                    status=403,
                )

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


def ab_test(
    flag_name: str,
    variants: dict[str, Callable] | None = None,
    default_variant: str = "control",
):
    """Decorator for A/B testing that routes to different implementations.

    Usage:
        @http_get("/checkout")
        @ab_test(
            "checkout_flow",
            variants={
                "control": checkout_v1,
                "variant_a": checkout_v2,
                "variant_b": checkout_v3,
            },
            default_variant="control",
        )
        def checkout(self, request):
            # This is called if no variant matches
            return checkout_v1(self, request)

    Args:
        flag_name: The name of the A/B test feature flag
        variants: Dictionary mapping variant names to handler functions
        default_variant: Default variant to use if flag is disabled
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            from .service import feature_flag_service

            # Extract user from request
            request = None
            user = None

            if args and hasattr(args[0], "user"):
                request = args[0]
            elif "request" in kwargs:
                request = kwargs["request"]

            if request and hasattr(request, "user") and request.user.is_authenticated:
                user = request.user

            # Get variant for user
            variant = feature_flag_service.get_variant(
                flag_name,
                user=user,
                default=default_variant,
            )

            # Log the variant assignment
            logger.debug(
                "A/B test '%s': user %s assigned to variant '%s'",
                flag_name,
                user.pk if user else "anonymous",
                variant,
            )

            # Add variant to kwargs for tracking
            kwargs["ab_variant"] = variant

            # If variants mapping provided and variant exists, use that handler
            if variants and variant in variants:
                return variants[variant](self, *args, **kwargs)

            # Otherwise use the decorated function
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


class FeatureFlagContext:
    """Context manager for temporarily enabling/disabling feature flags.

    Useful for testing and debugging.

    Usage:
        with FeatureFlagContext("new_feature", enabled=True):
            # Code here will see the feature as enabled
            pass
    """

    def __init__(self, flag_name: str, enabled: bool = True):
        """Initialize the context manager.

        Args:
            flag_name: The name of the feature flag
            enabled: Whether to enable or disable the flag
        """
        self.flag_name = flag_name
        self.enabled = enabled
        self.original_state: bool | None = None

    def __enter__(self) -> Self:
        """Enter the context and modify flag state."""
        from .service import feature_flag_service

        flag = feature_flag_service.get_flag(self.flag_name)
        if flag:
            self.original_state = flag.enabled
            flag.enabled = self.enabled
            flag.save(update_fields=["enabled"])
            feature_flag_service._invalidate_flag_cache(self.flag_name)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit the context and restore original flag state."""
        from .service import feature_flag_service

        if self.original_state is not None:
            flag = feature_flag_service.get_flag(self.flag_name)
            if flag:
                flag.enabled = self.original_state
                flag.save(update_fields=["enabled"])
                feature_flag_service._invalidate_flag_cache(self.flag_name)
