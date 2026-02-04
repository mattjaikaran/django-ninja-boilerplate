"""Feature Flag Service.

This module provides the FeatureFlagService for evaluating feature flags,
managing rollouts, and handling A/B testing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from core.services.base_service import CRUDService

from .models import FeatureFlag, FeatureFlagAuditLog, FlagType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

logger = logging.getLogger(__name__)

# Cache settings
FEATURE_FLAG_CACHE_PREFIX = "feature_flag"
FEATURE_FLAG_CACHE_TTL = getattr(settings, "FEATURE_FLAG_CACHE_TTL", 300)  # 5 minutes
ALL_FLAGS_CACHE_KEY = f"{FEATURE_FLAG_CACHE_PREFIX}:all"


class FeatureFlagService(CRUDService[FeatureFlag]):
    """Service for managing and evaluating feature flags.

    Provides methods for:
    - Checking if a flag is enabled for a user
    - Getting A/B test variants
    - Managing feature flag lifecycle
    - Caching for performance
    """

    model = FeatureFlag

    def _get_cache_key(self, flag_name: str) -> str:
        """Generate cache key for a feature flag."""
        return f"{FEATURE_FLAG_CACHE_PREFIX}:{flag_name}"

    def _get_user_cache_key(self, flag_name: str, user_id: str | UUID) -> str:
        """Generate cache key for user-specific flag evaluation."""
        return f"{FEATURE_FLAG_CACHE_PREFIX}:{flag_name}:user:{user_id}"

    def _get_from_cache(self, cache_key: str) -> Any | None:
        """Get value from cache with fallback."""
        try:
            return cache.get(cache_key)
        except Exception as e:
            logger.warning("Cache get failed: %s", e)
            return None

    def _set_in_cache(
        self, cache_key: str, value: Any, timeout: int = FEATURE_FLAG_CACHE_TTL
    ) -> None:
        """Set value in cache with fallback."""
        try:
            cache.set(cache_key, value, timeout)
        except Exception as e:
            logger.warning("Cache set failed: %s", e)

    def _delete_from_cache(self, cache_key: str) -> None:
        """Delete value from cache."""
        try:
            cache.delete(cache_key)
        except Exception as e:
            logger.warning("Cache delete failed: %s", e)

    def _invalidate_flag_cache(self, flag_name: str) -> None:
        """Invalidate all cache entries for a flag."""
        self._delete_from_cache(self._get_cache_key(flag_name))
        self._delete_from_cache(ALL_FLAGS_CACHE_KEY)
        # Note: User-specific cache entries will expire naturally
        # For full invalidation, consider using cache.delete_pattern if Redis is available

    def get_flag(self, flag_name: str) -> FeatureFlag | None:
        """Get a feature flag by name with caching.

        Args:
            flag_name: The name of the feature flag

        Returns:
            FeatureFlag instance or None if not found
        """
        cache_key = self._get_cache_key(flag_name)
        cached = self._get_from_cache(cache_key)

        if cached is not None:
            return cached if cached != "NOT_FOUND" else None

        try:
            flag = FeatureFlag.objects.get(name=flag_name)
            self._set_in_cache(cache_key, flag)
            return flag
        except FeatureFlag.DoesNotExist:
            self._set_in_cache(cache_key, "NOT_FOUND", timeout=60)  # Short TTL for misses
            return None

    def is_enabled(
        self,
        flag_name: str,
        user: AbstractUser | None = None,
        default: bool = False,
        environment: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Check if a feature flag is enabled for a user.

        Args:
            flag_name: The name of the feature flag
            user: The user to check the flag for (optional)
            default: Default value if flag doesn't exist
            environment: Override environment check
            context: Additional context for condition evaluation

        Returns:
            True if the flag is enabled, False otherwise
        """
        flag = self.get_flag(flag_name)

        if flag is None:
            logger.debug("Feature flag '%s' not found, returning default: %s", flag_name, default)
            return default

        # Master switch check
        if not flag.enabled:
            return False

        # Time window check
        if not flag.is_within_time_window():
            return False

        # Environment check
        if not flag.is_environment_active(environment):
            return False

        # User-specific checks
        if user is not None:
            user_id = str(user.pk)

            # Check if user is excluded
            if flag.is_user_excluded(user_id):
                return False

            # Check if user is in the enabled list
            if flag.flag_type == FlagType.USER_LIST.value:
                return flag.is_user_in_list(user_id)

            # Percentage rollout check
            if flag.flag_type == FlagType.PERCENTAGE.value:
                return self._check_percentage_rollout(flag, user_id)

            # For A/B tests, check if user would get a non-control variant
            if flag.flag_type == FlagType.AB_TEST.value:
                # A/B test is "enabled" if the user gets any variant
                return True

        # Condition evaluation
        if flag.conditions and context:
            if not self._evaluate_conditions(flag.conditions, context, user):
                return False

        # Default to enabled for boolean flags
        if flag.flag_type == FlagType.BOOLEAN.value:
            return True

        return flag.enabled

    def _check_percentage_rollout(self, flag: FeatureFlag, user_id: str) -> bool:
        """Check if user falls within the rollout percentage.

        Uses consistent hashing to ensure user always gets the same result.
        """
        if flag.rollout_percentage >= 100:
            return True
        if flag.rollout_percentage <= 0:
            return False

        # Consistent hash based on flag name and user id
        hash_input = f"{flag.name}:{user_id}"
        hash_value = hash(hash_input) % 100

        return hash_value < flag.rollout_percentage

    def _evaluate_conditions(
        self,
        conditions: dict[str, Any],
        context: dict[str, Any],
        user: AbstractUser | None = None,
    ) -> bool:
        """Evaluate advanced conditions for a flag.

        Supports conditions like:
        - user_attribute: {"is_staff": True, "email_domain": "company.com"}
        - context_match: {"plan": "premium"}
        """
        # User attribute conditions
        if "user_attributes" in conditions and user:
            for attr, expected in conditions["user_attributes"].items():
                actual = getattr(user, attr, None)

                # Handle special cases
                if attr == "email_domain" and hasattr(user, "email"):
                    actual = user.email.split("@")[-1] if user.email else None

                if actual != expected:
                    return False

        # Context match conditions
        if "context_match" in conditions:
            for key, expected in conditions["context_match"].items():
                if context.get(key) != expected:
                    return False

        return True

    def get_variant(
        self,
        flag_name: str,
        user: AbstractUser | None = None,
        default: str = "control",
    ) -> str:
        """Get the A/B test variant for a user.

        Args:
            flag_name: The name of the feature flag
            user: The user to get the variant for
            default: Default variant if flag doesn't exist or isn't enabled

        Returns:
            The variant name for the user
        """
        flag = self.get_flag(flag_name)

        if flag is None or not flag.enabled:
            return default

        if flag.flag_type != FlagType.AB_TEST.value:
            logger.warning("Flag '%s' is not an A/B test flag", flag_name)
            return default

        # Time and environment checks
        if not flag.is_within_time_window() or not flag.is_environment_active():
            return default

        if user is None:
            return flag.default_variant

        user_id = str(user.pk)

        # Check exclusions
        if flag.is_user_excluded(user_id):
            return default

        return flag.get_variant_for_user(user_id)

    def get_all_flags(self, enabled_only: bool = False) -> list[FeatureFlag]:
        """Get all feature flags with caching.

        Args:
            enabled_only: Only return enabled flags

        Returns:
            List of FeatureFlag instances
        """
        cache_key = f"{ALL_FLAGS_CACHE_KEY}:enabled" if enabled_only else ALL_FLAGS_CACHE_KEY
        cached = self._get_from_cache(cache_key)

        if cached is not None:
            return cached

        queryset = FeatureFlag.objects.all()
        if enabled_only:
            queryset = queryset.filter(enabled=True)

        flags = list(queryset)
        self._set_in_cache(cache_key, flags)
        return flags

    def get_flags_for_user(
        self,
        user: AbstractUser,
        environment: str | None = None,
    ) -> dict[str, bool | str]:
        """Get all feature flags status for a specific user.

        Returns a dictionary of flag names to their enabled status or variant.

        Args:
            user: The user to check flags for
            environment: Optional environment override

        Returns:
            Dictionary mapping flag names to enabled status or variant
        """
        result = {}
        flags = self.get_all_flags(enabled_only=True)

        for flag in flags:
            if flag.flag_type == FlagType.AB_TEST.value:
                result[flag.name] = self.get_variant(flag.name, user)
            else:
                result[flag.name] = self.is_enabled(
                    flag.name, user, environment=environment
                )

        return result

    def create_flag(
        self,
        name: str,
        description: str = "",
        flag_type: str = FlagType.BOOLEAN.value,
        enabled: bool = False,
        rollout_percentage: int = 0,
        variants: dict[str, int] | None = None,
        conditions: dict[str, Any] | None = None,
        user: AbstractUser | None = None,
        **kwargs: Any,
    ) -> FeatureFlag:
        """Create a new feature flag.

        Args:
            name: Unique name for the flag
            description: Description of the flag
            flag_type: Type of flag (boolean, percentage, user_list, ab_test)
            enabled: Whether the flag is enabled
            rollout_percentage: Percentage for gradual rollout
            variants: A/B test variants with weights
            conditions: Advanced conditions
            user: User creating the flag
            **kwargs: Additional fields

        Returns:
            Created FeatureFlag instance
        """
        data = {
            "name": name,
            "description": description,
            "flag_type": flag_type,
            "enabled": enabled,
            "rollout_percentage": rollout_percentage,
            "variants": variants or {},
            "conditions": conditions or {},
            **kwargs,
        }

        with transaction.atomic():
            flag = super().create(data, user)

            # Create audit log
            FeatureFlagAuditLog.objects.create(
                feature_flag=flag,
                action="created",
                changes={"initial_state": data},
                user=user,
            )

        self._invalidate_flag_cache(name)
        logger.info("Created feature flag: %s", name)
        return flag

    def update_flag(
        self,
        flag_id: str | UUID,
        data: dict[str, Any],
        user: AbstractUser | None = None,
    ) -> FeatureFlag:
        """Update a feature flag.

        Args:
            flag_id: The ID of the flag to update
            data: Dictionary of fields to update
            user: User performing the update

        Returns:
            Updated FeatureFlag instance
        """
        flag = self.get_by_id_or_raise(flag_id)
        old_data = {
            "name": flag.name,
            "enabled": flag.enabled,
            "rollout_percentage": flag.rollout_percentage,
            "flag_type": flag.flag_type,
        }

        with transaction.atomic():
            flag = super().update(flag_id, data, user)

            # Create audit log
            FeatureFlagAuditLog.objects.create(
                feature_flag=flag,
                action="updated",
                changes={"before": old_data, "after": data},
                user=user,
            )

        self._invalidate_flag_cache(flag.name)
        logger.info("Updated feature flag: %s", flag.name)
        return flag

    def toggle_flag(
        self,
        flag_name: str,
        enabled: bool | None = None,
        user: AbstractUser | None = None,
    ) -> FeatureFlag:
        """Toggle a feature flag on or off.

        Args:
            flag_name: The name of the flag to toggle
            enabled: Explicit enabled state (if None, toggles current state)
            user: User performing the toggle

        Returns:
            Updated FeatureFlag instance
        """
        flag = self.get_flag(flag_name)
        if flag is None:
            from api.exceptions import NotFoundError

            raise NotFoundError(f"Feature flag '{flag_name}' not found")

        new_state = not flag.enabled if enabled is None else enabled

        with transaction.atomic():
            flag.enabled = new_state
            if user:
                flag.updated_by = user
            flag.save(update_fields=["enabled", "updated_by", "updated_at"])

            # Create audit log
            action = "enabled" if new_state else "disabled"
            FeatureFlagAuditLog.objects.create(
                feature_flag=flag,
                action=action,
                changes={"enabled": new_state},
                user=user,
            )

        self._invalidate_flag_cache(flag_name)
        logger.info("Toggled feature flag '%s' to %s", flag_name, new_state)
        return flag

    def set_rollout_percentage(
        self,
        flag_name: str,
        percentage: int,
        user: AbstractUser | None = None,
    ) -> FeatureFlag:
        """Set the rollout percentage for a flag.

        Args:
            flag_name: The name of the flag
            percentage: New rollout percentage (0-100)
            user: User performing the update

        Returns:
            Updated FeatureFlag instance
        """
        if not 0 <= percentage <= 100:
            from api.exceptions import ValidationError

            raise ValidationError("Percentage must be between 0 and 100")

        flag = self.get_flag(flag_name)
        if flag is None:
            from api.exceptions import NotFoundError

            raise NotFoundError(f"Feature flag '{flag_name}' not found")

        old_percentage = flag.rollout_percentage

        with transaction.atomic():
            flag.rollout_percentage = percentage
            flag.flag_type = FlagType.PERCENTAGE.value
            if user:
                flag.updated_by = user
            flag.save(update_fields=["rollout_percentage", "flag_type", "updated_by", "updated_at"])

            # Create audit log
            FeatureFlagAuditLog.objects.create(
                feature_flag=flag,
                action="rollout_updated",
                changes={
                    "old_percentage": old_percentage,
                    "new_percentage": percentage,
                },
                user=user,
            )

        self._invalidate_flag_cache(flag_name)
        logger.info(
            "Updated rollout percentage for '%s' from %d%% to %d%%",
            flag_name,
            old_percentage,
            percentage,
        )
        return flag

    def add_user_to_flag(
        self,
        flag_name: str,
        user_id: str | UUID,
        admin_user: AbstractUser | None = None,
    ) -> FeatureFlag:
        """Add a user to a feature flag's enabled list.

        Args:
            flag_name: The name of the flag
            user_id: The user ID to add
            admin_user: Admin user performing the action

        Returns:
            Updated FeatureFlag instance
        """
        flag = self.get_flag(flag_name)
        if flag is None:
            from api.exceptions import NotFoundError

            raise NotFoundError(f"Feature flag '{flag_name}' not found")

        flag.add_user(str(user_id))

        # Create audit log
        FeatureFlagAuditLog.objects.create(
            feature_flag=flag,
            action="user_added",
            changes={"user_id": str(user_id)},
            user=admin_user,
        )

        self._invalidate_flag_cache(flag_name)
        return flag

    def remove_user_from_flag(
        self,
        flag_name: str,
        user_id: str | UUID,
        admin_user: AbstractUser | None = None,
    ) -> FeatureFlag:
        """Remove a user from a feature flag's enabled list.

        Args:
            flag_name: The name of the flag
            user_id: The user ID to remove
            admin_user: Admin user performing the action

        Returns:
            Updated FeatureFlag instance
        """
        flag = self.get_flag(flag_name)
        if flag is None:
            from api.exceptions import NotFoundError

            raise NotFoundError(f"Feature flag '{flag_name}' not found")

        flag.remove_user(str(user_id))

        # Create audit log
        FeatureFlagAuditLog.objects.create(
            feature_flag=flag,
            action="user_removed",
            changes={"user_id": str(user_id)},
            user=admin_user,
        )

        self._invalidate_flag_cache(flag_name)
        return flag

    def delete_flag(
        self,
        flag_id: str | UUID,
        user: AbstractUser | None = None,
        hard_delete: bool = True,
    ) -> bool:
        """Delete a feature flag.

        Args:
            flag_id: The ID of the flag to delete
            user: User performing the deletion
            hard_delete: Always hard delete for flags

        Returns:
            True if deleted successfully
        """
        flag = self.get_by_id_or_raise(flag_id)
        flag_name = flag.name

        # Delete the flag
        flag.delete()

        self._invalidate_flag_cache(flag_name)
        logger.info("Deleted feature flag: %s", flag_name)
        return True


# Singleton instance for convenience
feature_flag_service = FeatureFlagService()
