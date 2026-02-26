"""Task result and dead letter queue models.

This module provides Django models for:
- Persistent task result tracking
- Dead letter queue for failed tasks
"""

import uuid
from datetime import timedelta

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone


class TaskStatus(models.TextChoices):
    """Task execution status choices."""

    PENDING = "pending", "Pending"
    STARTED = "started", "Started"
    PROGRESS = "progress", "In Progress"
    SUCCESS = "success", "Success"
    FAILURE = "failure", "Failure"
    RETRY = "retry", "Retrying"
    REVOKED = "revoked", "Revoked"


class TaskResult(models.Model):
    """Model for tracking Celery task results and progress.

    This model stores task execution details including:
    - Task identification (id, name)
    - Execution status and progress
    - Input arguments and output result
    - Error information
    - Timing information
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this record",
    )

    task_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Celery task ID",
    )

    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Task name (e.g., 'core.tasks.send_email')",
    )

    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        db_index=True,
        help_text="Current task status",
    )

    progress = models.IntegerField(
        default=0,
        help_text="Task progress percentage (0-100)",
    )

    progress_message = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Current progress message",
    )

    args = models.JSONField(
        default=list,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Task positional arguments",
    )

    kwargs = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Task keyword arguments",
    )

    result = models.JSONField(
        null=True,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Task result data",
    )

    error = models.TextField(
        blank=True,
        default="",
        help_text="Error message if task failed",
    )

    traceback = models.TextField(
        blank=True,
        default="",
        help_text="Full traceback if task failed",
    )

    meta = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Additional metadata",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the task was created",
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the task started execution",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the task completed (success or failure)",
    )

    class Meta:
        db_table = "core_task_result"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["name", "-created_at"]),
        ]
        verbose_name = "Task Result"
        verbose_name_plural = "Task Results"

    def __str__(self) -> str:
        return f"{self.name} ({self.task_id}) - {self.status}"

    @property
    def duration(self) -> float | None:
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        if self.started_at:
            return (timezone.now() - self.started_at).total_seconds()
        return None

    @property
    def is_complete(self) -> bool:
        """Check if task has completed (success or failure)."""
        return self.status in [
            TaskStatus.SUCCESS,
            TaskStatus.FAILURE,
            TaskStatus.REVOKED,
        ]

    @property
    def is_successful(self) -> bool:
        """Check if task completed successfully."""
        return self.status == TaskStatus.SUCCESS

    def mark_revoked(self) -> None:
        """Mark the task as revoked."""
        self.status = TaskStatus.REVOKED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])

    @classmethod
    def cleanup_old_results(cls, days: int = 30) -> int:
        """Delete task results older than specified days.

        Args:
            days: Number of days to keep results

        Returns:
            Number of deleted records
        """
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = cls.objects.filter(created_at__lt=cutoff).delete()
        return deleted


class DeadLetterQueueEntry(models.Model):
    """Model for storing failed tasks in a dead letter queue.

    Failed tasks that have exhausted retries are stored here for:
    - Manual inspection
    - Later retry
    - Analysis and debugging
    """

    class Priority(models.TextChoices):
        """Priority levels for DLQ entries."""

        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    task_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Original Celery task ID",
    )

    task_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Task name",
    )

    args = models.JSONField(
        default=list,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Task positional arguments",
    )

    kwargs = models.JSONField(
        default=dict,
        blank=True,
        encoder=DjangoJSONEncoder,
        help_text="Task keyword arguments",
    )

    exception_type = models.CharField(
        max_length=255,
        help_text="Exception class name",
    )

    exception_message = models.TextField(
        help_text="Exception message",
    )

    traceback = models.TextField(
        blank=True,
        default="",
        help_text="Full traceback",
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
        db_index=True,
        help_text="Priority level for retry",
    )

    retry_count = models.IntegerField(
        default=0,
        help_text="Number of retry attempts from DLQ",
    )

    max_retries = models.IntegerField(
        default=3,
        help_text="Maximum retry attempts from DLQ",
    )

    last_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last retry was attempted",
    )

    is_resolved = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this entry has been resolved",
    )

    resolution_notes = models.TextField(
        blank=True,
        default="",
        help_text="Notes about how this was resolved",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "core_dead_letter_queue"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_resolved", "-created_at"]),
            models.Index(fields=["priority", "-created_at"]),
            models.Index(fields=["task_name", "-created_at"]),
        ]
        verbose_name = "Dead Letter Queue Entry"
        verbose_name_plural = "Dead Letter Queue Entries"

    def __str__(self) -> str:
        return f"{self.task_name} ({self.task_id}) - {'Resolved' if self.is_resolved else 'Pending'}"

    @property
    def can_retry(self) -> bool:
        """Check if this entry can be retried."""
        return not self.is_resolved and self.retry_count < self.max_retries

    def mark_resolved(self, notes: str = "") -> None:
        """Mark this entry as resolved.

        Args:
            notes: Optional resolution notes
        """
        self.is_resolved = True
        self.resolution_notes = notes
        self.save(update_fields=["is_resolved", "resolution_notes", "updated_at"])

    @classmethod
    def get_pending_count(cls) -> int:
        """Get count of pending (unresolved) entries."""
        return cls.objects.filter(is_resolved=False).count()

    @classmethod
    def cleanup_resolved(cls, days: int = 30) -> int:
        """Delete resolved entries older than specified days.

        Args:
            days: Number of days to keep resolved entries

        Returns:
            Number of deleted records
        """
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = cls.objects.filter(
            is_resolved=True,
            updated_at__lt=cutoff,
        ).delete()
        return deleted
