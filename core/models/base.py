"""Base model classes for the application.

This module provides abstract base models that all models should inherit from.
Includes soft delete support, metadata tracking, and audit fields.
"""

import uuid
from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone


class AbstractBaseModel(models.Model):
    """Abstract base model with common fields for all models.

    Provides:
        - UUID primary key
        - Created/updated timestamps with indexes
        - Created by/updated by user tracking
        - Soft delete via is_active flag
        - JSON metadata field for flexible additional data
        - Utility methods for soft delete, restore, and metadata management
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this record",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this record was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="When this record was last updated",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
        help_text="User who created this record",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
        help_text="User who last updated this record",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this record is active (soft delete)",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Additional metadata for this record",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["-updated_at"]),
            models.Index(fields=["is_active"]),
        ]

    def save(self, *args, **kwargs) -> None:
        """Override save to handle common logic."""
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def soft_delete(self, user=None) -> None:
        """Soft delete this record by setting is_active to False.

        Args:
            user: User performing the deletion
        """
        self.is_active = False
        if user:
            self.updated_by = user
        self.save(update_fields=["is_active", "updated_by", "updated_at"])

    def restore(self, user=None) -> None:
        """Restore a soft-deleted record by setting is_active to True.

        Args:
            user: User performing the restoration
        """
        self.is_active = True
        if user:
            self.updated_by = user
        self.save(update_fields=["is_active", "updated_by", "updated_at"])

    def set_metadata(self, key: str, value: Any, user=None) -> None:
        """Set a metadata key-value pair.

        Args:
            key: Metadata key
            value: Metadata value
            user: User performing the update
        """
        if self.metadata is None:
            self.metadata = {}

        self.metadata[key] = value

        if user:
            self.updated_by = user

        self.save(update_fields=["metadata", "updated_by", "updated_at"])

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata value by key.

        Args:
            key: Metadata key
            default: Default value if key doesn't exist

        Returns:
            Metadata value or default
        """
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)

    def remove_metadata(self, key: str, user=None) -> None:
        """Remove a metadata key.

        Args:
            key: Metadata key to remove
            user: User performing the update
        """
        if self.metadata and key in self.metadata:
            del self.metadata[key]

            if user:
                self.updated_by = user

            self.save(update_fields=["metadata", "updated_by", "updated_at"])

    def update_metadata(self, updates: dict, user=None) -> None:
        """Bulk update metadata with a dictionary.

        Args:
            updates: Dictionary of key-value pairs to update
            user: User performing the update
        """
        if self.metadata is None:
            self.metadata = {}

        self.metadata.update(updates)

        if user:
            self.updated_by = user

        self.save(update_fields=["metadata", "updated_by", "updated_at"])

    @property
    def age(self):
        """Get the age of this record as a timedelta.

        Returns:
            timedelta: Age of the record
        """
        return timezone.now() - self.created_at

    @property
    def time_since_updated(self):
        """Get the time since last update as a timedelta.

        Returns:
            timedelta: Time since last update
        """
        return timezone.now() - self.updated_at

    def __str__(self) -> str:
        """String representation of the model.

        Returns the model name and ID by default.
        Override in subclasses for better representation.
        """
        return f"{self.__class__.__name__} ({self.id})"


class ActiveManager(models.Manager):
    """Manager that only returns active records (is_active=True)."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SoftDeleteModel(AbstractBaseModel):
    """Base model that includes soft delete functionality with custom managers.

    This model provides:
    - All AbstractBaseModel functionality
    - ActiveManager as default manager (only returns active records)
    - all_objects manager for accessing all records including deleted
    - deleted_objects manager for accessing only deleted records
    """

    objects = ActiveManager()  # Default manager (only active records)
    all_objects = models.Manager()  # Manager for all records
    deleted_objects: models.Manager  # Will be set dynamically

    class Meta:
        abstract = True

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Create deleted_objects manager dynamically
        cls.deleted_objects = DeletedManager()


class DeletedManager(models.Manager):
    """Manager that only returns soft-deleted records (is_active=False)."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=False)


class TimestampedModel(models.Model):
    """Simple model with just timestamps (no soft delete or metadata).

    Use this for models that don't need the full AbstractBaseModel features.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
