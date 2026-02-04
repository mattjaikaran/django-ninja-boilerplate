"""Feature Flag models.

This module defines the FeatureFlag model for managing feature toggles,
gradual rollouts, and A/B testing.
"""

import uuid
from enum import Enum

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class FlagType(str, Enum):
    """Types of feature flags."""

    BOOLEAN = "boolean"  # Simple on/off toggle
    PERCENTAGE = "percentage"  # Gradual rollout
    USER_LIST = "user_list"  # Specific users only
    AB_TEST = "ab_test"  # A/B testing with variants


class FeatureFlag(models.Model):
    """Feature flag model for managing feature toggles.

    Supports:
    - Simple boolean toggles
    - Percentage-based rollouts
    - User-specific flags
    - A/B testing with multiple variants
    - Environment-specific settings
    - Time-based activation
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this feature flag",
    )

    # Core fields
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique name for this feature flag (use snake_case)",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Description of what this feature flag controls",
    )

    # Flag type and state
    flag_type = models.CharField(
        max_length=20,
        choices=[(t.value, t.name) for t in FlagType],
        default=FlagType.BOOLEAN.value,
        help_text="Type of feature flag",
    )
    enabled = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Master switch - if False, flag is disabled for everyone",
    )

    # Rollout settings
    rollout_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of users to enable this flag for (0-100)",
    )

    # User targeting
    user_ids = models.JSONField(
        default=list,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="List of user IDs that have this flag enabled",
    )
    excluded_user_ids = models.JSONField(
        default=list,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="List of user IDs that are excluded from this flag",
    )

    # A/B Testing
    variants = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="A/B test variants with weights, e.g., {'control': 50, 'variant_a': 30, 'variant_b': 20}",
    )
    default_variant = models.CharField(
        max_length=50,
        blank=True,
        default="control",
        help_text="Default variant for A/B tests",
    )

    # Advanced conditions
    conditions = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Advanced conditions for flag evaluation (e.g., user attributes, environment)",
    )

    # Environment settings
    environments = models.JSONField(
        default=list,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="List of environments where this flag is active (empty = all)",
    )

    # Time-based activation
    starts_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this flag should start being active",
    )
    ends_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this flag should stop being active",
    )

    # Metadata and tracking
    metadata = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Additional metadata for this flag",
    )
    tags = models.JSONField(
        default=list,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Tags for organizing and filtering flags",
    )

    # Audit fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this flag was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this flag was last updated",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_feature_flags",
        help_text="User who created this flag",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_feature_flags",
        help_text="User who last updated this flag",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Feature Flag"
        verbose_name_plural = "Feature Flags"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["enabled"]),
            models.Index(fields=["flag_type"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"{self.name} ({status})"

    def is_within_time_window(self) -> bool:
        """Check if current time is within the flag's activation window."""
        now = timezone.now()

        if self.starts_at and now < self.starts_at:
            return False

        return not (self.ends_at and now > self.ends_at)

    def is_environment_active(self, environment: str | None = None) -> bool:
        """Check if flag is active for the given environment."""
        if not self.environments:
            return True

        if environment is None:
            environment = getattr(settings, "ENVIRONMENT", "development")

        return environment in self.environments

    def is_user_in_list(self, user_id: str) -> bool:
        """Check if a user ID is in the enabled users list."""
        return str(user_id) in [str(uid) for uid in self.user_ids]

    def is_user_excluded(self, user_id: str) -> bool:
        """Check if a user ID is in the excluded users list."""
        return str(user_id) in [str(uid) for uid in self.excluded_user_ids]

    def get_variant_for_user(self, user_id: str) -> str:
        """Get the A/B test variant for a specific user.

        Uses consistent hashing to ensure users always get the same variant.
        """
        if not self.variants:
            return self.default_variant

        # Create a consistent hash from flag name and user id
        hash_input = f"{self.name}:{user_id}"
        hash_value = hash(hash_input) % 100

        # Calculate cumulative weights and find variant
        cumulative = 0
        for variant, weight in self.variants.items():
            cumulative += weight
            if hash_value < cumulative:
                return variant

        return self.default_variant

    def add_user(self, user_id: str) -> None:
        """Add a user to the enabled users list."""
        user_id_str = str(user_id)
        if user_id_str not in [str(uid) for uid in self.user_ids]:
            self.user_ids.append(user_id_str)
            self.save(update_fields=["user_ids", "updated_at"])

    def remove_user(self, user_id: str) -> None:
        """Remove a user from the enabled users list."""
        user_id_str = str(user_id)
        self.user_ids = [uid for uid in self.user_ids if str(uid) != user_id_str]
        self.save(update_fields=["user_ids", "updated_at"])

    def exclude_user(self, user_id: str) -> None:
        """Add a user to the excluded users list."""
        user_id_str = str(user_id)
        if user_id_str not in [str(uid) for uid in self.excluded_user_ids]:
            self.excluded_user_ids.append(user_id_str)
            self.save(update_fields=["excluded_user_ids", "updated_at"])

    def unexclude_user(self, user_id: str) -> None:
        """Remove a user from the excluded users list."""
        user_id_str = str(user_id)
        self.excluded_user_ids = [
            uid for uid in self.excluded_user_ids if str(uid) != user_id_str
        ]
        self.save(update_fields=["excluded_user_ids", "updated_at"])


class FeatureFlagAuditLog(models.Model):
    """Audit log for feature flag changes."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    feature_flag = models.ForeignKey(
        FeatureFlag,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(
        max_length=50,
        help_text="Action performed (created, updated, deleted, enabled, disabled)",
    )
    changes = models.JSONField(
        default=dict,
        encoder=DjangoJSONEncoder,
        help_text="Details of the changes made",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Feature Flag Audit Log"
        verbose_name_plural = "Feature Flag Audit Logs"

    def __str__(self) -> str:
        return f"{self.feature_flag.name} - {self.action} at {self.created_at}"
