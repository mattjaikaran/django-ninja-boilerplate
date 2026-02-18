"""Base model classes for the application.

This module provides a tiered hierarchy of abstract base models:

- TimestampedModel: UUID pk + timestamps (lightweight, for simple models)
- AuditBaseModel(TimestampedModel): Adds created_by/updated_by tracking
- SoftDeleteBaseModel(AuditBaseModel): Adds soft delete + metadata
- AbstractBaseModel: Alias for SoftDeleteBaseModel (backwards compatible)

Existing models can use any tier. New models default to TimestampedModel
unless they need audit trails or soft delete.
"""

import uuid
from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone

# =============================================================================
# Tier 1: UUID + Timestamps (lightweight default)
# =============================================================================


class TimestampedModel(models.Model):
    """Simple model with UUID pk and timestamps.

    Use this for models that don't need audit trails or soft delete.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    @property
    def age(self):
        """Get the age of this record as a timedelta."""
        return timezone.now() - self.created_at

    def __str__(self) -> str:
        return f"{self.__class__.__name__} ({self.id})"


# =============================================================================
# Tier 2: Audit tracking (created_by / updated_by)
# =============================================================================


class AuditBaseModel(TimestampedModel):
    """Model with audit tracking fields.

    Adds created_by/updated_by ForeignKeys on top of TimestampedModel.
    Use this for models where you need to track who made changes.
    """

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

    class Meta:
        abstract = True
        ordering = ["-created_at"]


# =============================================================================
# Tier 3: Soft delete + metadata (full featured)
# =============================================================================


class ActiveManager(models.Manager):
    """Manager that only returns active records (is_active=True)."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class DeletedManager(models.Manager):
    """Manager that only returns soft-deleted records (is_active=False)."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=False)


class SoftDeleteBaseModel(AuditBaseModel):
    """Full-featured model with soft delete, metadata, and audit tracking.

    Provides:
        - UUID pk, timestamps, audit tracking (from parent classes)
        - is_active flag for soft delete with dedicated managers
        - deleted_at / deleted_by tracking
        - JSON metadata field for flexible additional data
        - soft_delete() / restore() / hard_delete() methods
    """

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this record is active (soft delete)",
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this record was soft-deleted",
    )

    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_deleted",
        help_text="User who deleted this record",
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
            models.Index(fields=["is_active"]),
            models.Index(fields=["-created_at"]),
        ]

    def soft_delete(self, user=None) -> None:
        """Soft delete this record."""
        self.is_active = False
        self.deleted_at = timezone.now()
        update_fields = ["is_active", "deleted_at", "updated_at"]
        if user:
            self.deleted_by = user
            self.updated_by = user
            update_fields.extend(["deleted_by", "updated_by"])
        self.save(update_fields=update_fields)

    def restore(self, user=None) -> None:
        """Restore a soft-deleted record."""
        self.is_active = True
        self.deleted_at = None
        self.deleted_by = None
        update_fields = ["is_active", "deleted_at", "deleted_by", "updated_at"]
        if user:
            self.updated_by = user
            update_fields.append("updated_by")
        self.save(update_fields=update_fields)

    def hard_delete(self):
        """Permanently delete this record from the database."""
        super().delete()

    def set_metadata(self, key: str, value: Any, user=None) -> None:
        """Set a metadata key-value pair."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
        update_fields = ["metadata", "updated_at"]
        if user:
            self.updated_by = user
            update_fields.append("updated_by")
        self.save(update_fields=update_fields)

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata value by key."""
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)

    def remove_metadata(self, key: str, user=None) -> None:
        """Remove a metadata key."""
        if self.metadata and key in self.metadata:
            del self.metadata[key]
            update_fields = ["metadata", "updated_at"]
            if user:
                self.updated_by = user
                update_fields.append("updated_by")
            self.save(update_fields=update_fields)

    def update_metadata(self, updates: dict, user=None) -> None:
        """Bulk update metadata with a dictionary."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata.update(updates)
        update_fields = ["metadata", "updated_at"]
        if user:
            self.updated_by = user
            update_fields.append("updated_by")
        self.save(update_fields=update_fields)


class SoftDeleteModel(SoftDeleteBaseModel):
    """Soft delete model with custom default managers.

    Uses ActiveManager as the default manager (only returns active records).
    Use all_objects to access all records including deleted ones.
    """

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True


# =============================================================================
# Backwards Compatibility
# =============================================================================

# AbstractBaseModel is an alias for SoftDeleteBaseModel
# for backwards compatibility with existing code
AbstractBaseModel = SoftDeleteBaseModel
