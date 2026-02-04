"""Dead Letter Queue handling for failed tasks.

This module provides utilities for managing failed tasks that have
exhausted their retry attempts, allowing for manual inspection,
retry, and resolution.
"""

import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """Manager class for Dead Letter Queue operations.

    Provides methods to:
    - Add failed tasks to the DLQ
    - List and filter DLQ entries
    - Retry failed tasks
    - Mark entries as resolved
    """

    @classmethod
    def add_failed_task(
        cls,
        task_id: str,
        task_name: str,
        args: tuple | list,
        kwargs: dict,
        exception: Exception,
        traceback: str | None = None,
        priority: str = "normal",
    ) -> dict | None:
        """Add a failed task to the Dead Letter Queue.

        Args:
            task_id: The Celery task ID
            task_name: The task name/path
            args: Task positional arguments
            kwargs: Task keyword arguments
            exception: The exception that caused the failure
            traceback: Optional full traceback string
            priority: Priority level ('low', 'normal', 'high', 'critical')

        Returns:
            Created DLQ entry dictionary or None on failure
        """
        from core.tasks.models import DeadLetterQueueEntry

        try:
            entry = DeadLetterQueueEntry.objects.create(
                task_id=task_id,
                task_name=task_name,
                args=list(args) if args else [],
                kwargs=kwargs or {},
                exception_type=type(exception).__name__,
                exception_message=str(exception),
                traceback=traceback or "",
                priority=priority,
            )

            logger.warning(
                "Task added to DLQ: %s (%s) - %s",
                task_name,
                task_id,
                exception,
            )

            return cls._entry_to_dict(entry)

        except Exception as e:
            logger.error("Failed to add task to DLQ: %s", e)
            return None

    @classmethod
    def list_entries(
        cls,
        include_resolved: bool = False,
        priority: str | None = None,
        task_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """List DLQ entries with optional filtering.

        Args:
            include_resolved: Whether to include resolved entries
            priority: Filter by priority level
            task_name: Filter by task name (partial match)
            limit: Maximum number of entries to return
            offset: Number of entries to skip

        Returns:
            List of DLQ entry dictionaries
        """
        from core.tasks.models import DeadLetterQueueEntry

        try:
            queryset = DeadLetterQueueEntry.objects.all()

            if not include_resolved:
                queryset = queryset.filter(is_resolved=False)

            if priority:
                queryset = queryset.filter(priority=priority)

            if task_name:
                queryset = queryset.filter(task_name__icontains=task_name)

            entries = queryset.order_by("-created_at")[offset : offset + limit]

            return [cls._entry_to_dict(entry) for entry in entries]

        except Exception as e:
            logger.error("Failed to list DLQ entries: %s", e)
            return []

    @classmethod
    def get_entry(cls, entry_id: str) -> dict | None:
        """Get a specific DLQ entry by ID.

        Args:
            entry_id: The DLQ entry UUID

        Returns:
            Entry dictionary or None if not found
        """
        from core.tasks.models import DeadLetterQueueEntry

        try:
            entry = DeadLetterQueueEntry.objects.get(id=entry_id)
            return cls._entry_to_dict(entry)
        except DeadLetterQueueEntry.DoesNotExist:
            return None
        except Exception as e:
            logger.error("Failed to get DLQ entry %s: %s", entry_id, e)
            return None

    @classmethod
    def retry_entry(cls, entry_id: str) -> str | None:
        """Retry a DLQ entry by re-queuing the task.

        Args:
            entry_id: The DLQ entry UUID

        Returns:
            New task ID or None on failure
        """
        from celery import current_app

        from core.tasks.models import DeadLetterQueueEntry

        try:
            with transaction.atomic():
                entry = DeadLetterQueueEntry.objects.select_for_update().get(
                    id=entry_id
                )

                if entry.is_resolved:
                    logger.warning("Cannot retry resolved entry: %s", entry_id)
                    return None

                if not entry.can_retry:
                    logger.warning(
                        "Entry %s has exceeded max retries (%d/%d)",
                        entry_id,
                        entry.retry_count,
                        entry.max_retries,
                    )
                    return None

                # Send the task
                result = current_app.send_task(
                    entry.task_name,
                    args=entry.args,
                    kwargs=entry.kwargs,
                )

                # Update entry
                entry.retry_count += 1
                entry.last_retry_at = timezone.now()
                entry.save(update_fields=["retry_count", "last_retry_at", "updated_at"])

                logger.info(
                    "Retried DLQ entry %s: new_task_id=%s",
                    entry_id,
                    result.id,
                )

                return result.id

        except DeadLetterQueueEntry.DoesNotExist:
            logger.error("DLQ entry not found: %s", entry_id)
            return None
        except Exception as e:
            logger.error("Failed to retry DLQ entry %s: %s", entry_id, e)
            return None

    @classmethod
    def retry_all_pending(
        cls,
        task_name: str | None = None,
        priority: str | None = None,
        limit: int = 10,
    ) -> dict:
        """Retry all pending DLQ entries that can be retried.

        Args:
            task_name: Optional filter by task name
            priority: Optional filter by priority
            limit: Maximum number of entries to retry

        Returns:
            Dictionary with retry results
        """
        from core.tasks.models import DeadLetterQueueEntry

        results = {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "task_ids": [],
            "errors": [],
        }

        try:
            queryset = DeadLetterQueueEntry.objects.filter(
                is_resolved=False,
            ).exclude(
                retry_count__gte=models.F("max_retries"),
            )

            if task_name:
                queryset = queryset.filter(task_name__icontains=task_name)

            if priority:
                queryset = queryset.filter(priority=priority)

            entries = queryset.order_by("-priority", "created_at")[:limit]

            for entry in entries:
                results["attempted"] += 1

                task_id = cls.retry_entry(str(entry.id))
                if task_id:
                    results["succeeded"] += 1
                    results["task_ids"].append(task_id)
                else:
                    results["failed"] += 1
                    results["errors"].append(
                        {
                            "entry_id": str(entry.id),
                            "error": "Retry failed",
                        }
                    )

            return results

        except Exception as e:
            logger.error("Failed to retry pending DLQ entries: %s", e)
            results["errors"].append({"error": str(e)})
            return results

    @classmethod
    def resolve_entry(
        cls,
        entry_id: str,
        notes: str = "",
    ) -> dict | None:
        """Mark a DLQ entry as resolved.

        Args:
            entry_id: The DLQ entry UUID
            notes: Optional resolution notes

        Returns:
            Updated entry dictionary or None on failure
        """
        from core.tasks.models import DeadLetterQueueEntry

        try:
            entry = DeadLetterQueueEntry.objects.get(id=entry_id)
            entry.mark_resolved(notes)

            logger.info("Resolved DLQ entry: %s", entry_id)
            return cls._entry_to_dict(entry)

        except DeadLetterQueueEntry.DoesNotExist:
            logger.error("DLQ entry not found: %s", entry_id)
            return None
        except Exception as e:
            logger.error("Failed to resolve DLQ entry %s: %s", entry_id, e)
            return None

    @classmethod
    def bulk_resolve(
        cls,
        entry_ids: list[str],
        notes: str = "",
    ) -> dict:
        """Resolve multiple DLQ entries.

        Args:
            entry_ids: List of DLQ entry UUIDs
            notes: Optional resolution notes

        Returns:
            Dictionary with resolution results
        """
        from core.tasks.models import DeadLetterQueueEntry

        results = {
            "attempted": len(entry_ids),
            "succeeded": 0,
            "failed": 0,
            "errors": [],
        }

        try:
            with transaction.atomic():
                updated = DeadLetterQueueEntry.objects.filter(
                    id__in=entry_ids,
                    is_resolved=False,
                ).update(
                    is_resolved=True,
                    resolution_notes=notes,
                    updated_at=timezone.now(),
                )

                results["succeeded"] = updated
                results["failed"] = len(entry_ids) - updated

            logger.info("Bulk resolved %d DLQ entries", updated)
            return results

        except Exception as e:
            logger.error("Failed to bulk resolve DLQ entries: %s", e)
            results["errors"].append({"error": str(e)})
            return results

    @classmethod
    def delete_entry(cls, entry_id: str) -> bool:
        """Permanently delete a DLQ entry.

        Args:
            entry_id: The DLQ entry UUID

        Returns:
            True if deleted, False otherwise
        """
        from core.tasks.models import DeadLetterQueueEntry

        try:
            entry = DeadLetterQueueEntry.objects.get(id=entry_id)
            entry.delete()

            logger.info("Deleted DLQ entry: %s", entry_id)
            return True

        except DeadLetterQueueEntry.DoesNotExist:
            return False
        except Exception as e:
            logger.error("Failed to delete DLQ entry %s: %s", entry_id, e)
            return False

    @classmethod
    def get_stats(cls) -> dict:
        """Get DLQ statistics.

        Returns:
            Dictionary with DLQ statistics
        """
        from django.db.models import Count, Q

        from core.tasks.models import DeadLetterQueueEntry

        try:
            stats = DeadLetterQueueEntry.objects.aggregate(
                total=Count("id"),
                pending=Count("id", filter=Q(is_resolved=False)),
                resolved=Count("id", filter=Q(is_resolved=True)),
                low_priority=Count(
                    "id",
                    filter=Q(is_resolved=False, priority="low"),
                ),
                normal_priority=Count(
                    "id",
                    filter=Q(is_resolved=False, priority="normal"),
                ),
                high_priority=Count(
                    "id",
                    filter=Q(is_resolved=False, priority="high"),
                ),
                critical_priority=Count(
                    "id",
                    filter=Q(is_resolved=False, priority="critical"),
                ),
            )

            # Get entries that can still be retried
            from django.db.models import F

            stats["can_retry"] = DeadLetterQueueEntry.objects.filter(
                is_resolved=False,
                retry_count__lt=F("max_retries"),
            ).count()

            # Get entries that have exhausted retries
            stats["exhausted_retries"] = DeadLetterQueueEntry.objects.filter(
                is_resolved=False,
                retry_count__gte=F("max_retries"),
            ).count()

            # Get most common failed tasks
            task_counts = (
                DeadLetterQueueEntry.objects.filter(is_resolved=False)
                .values("task_name")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            )
            stats["top_failed_tasks"] = list(task_counts)

            return stats

        except Exception as e:
            logger.error("Failed to get DLQ stats: %s", e)
            return {}

    @classmethod
    def cleanup(cls, days: int = 30) -> dict:
        """Clean up old resolved DLQ entries.

        Args:
            days: Delete resolved entries older than this many days

        Returns:
            Dictionary with cleanup results
        """
        from core.tasks.models import DeadLetterQueueEntry

        try:
            deleted = DeadLetterQueueEntry.cleanup_resolved(days=days)

            logger.info("Cleaned up %d resolved DLQ entries", deleted)

            return {
                "deleted": deleted,
                "days_threshold": days,
            }

        except Exception as e:
            logger.error("Failed to cleanup DLQ: %s", e)
            return {"error": str(e)}

    @classmethod
    def _entry_to_dict(cls, entry) -> dict:
        """Convert a DeadLetterQueueEntry to a dictionary.

        Args:
            entry: DeadLetterQueueEntry model instance

        Returns:
            Dictionary representation
        """
        return {
            "id": str(entry.id),
            "task_id": entry.task_id,
            "task_name": entry.task_name,
            "args": entry.args,
            "kwargs": entry.kwargs,
            "exception_type": entry.exception_type,
            "exception_message": entry.exception_message,
            "traceback": entry.traceback,
            "priority": entry.priority,
            "retry_count": entry.retry_count,
            "max_retries": entry.max_retries,
            "can_retry": entry.can_retry,
            "last_retry_at": (
                entry.last_retry_at.isoformat() if entry.last_retry_at else None
            ),
            "is_resolved": entry.is_resolved,
            "resolution_notes": entry.resolution_notes,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
        }


# Import models at module level for retry_all_pending
from django.db import models
