"""Task progress tracking utilities.

This module provides utilities for tracking and retrieving task progress,
using both Redis (for real-time updates) and database (for persistence).
"""

import logging
from typing import Any

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cache key prefix for task progress
PROGRESS_CACHE_PREFIX = "task_progress:"
PROGRESS_CACHE_TIMEOUT = 3600  # 1 hour


class TaskProgressTracker:
    """Utility class for tracking task progress.

    Provides methods to update and retrieve task progress from both
    Redis cache (for speed) and database (for persistence).
    """

    @classmethod
    def update_progress(
        cls,
        task_id: str,
        progress: int,
        message: str = "",
        meta: dict | None = None,
    ) -> None:
        """Update task progress in cache and database.

        Args:
            task_id: The Celery task ID
            progress: Progress percentage (0-100)
            message: Optional progress message
            meta: Optional metadata dictionary
        """
        from core.tasks.models import TaskResult, TaskStatus

        progress = min(100, max(0, progress))
        progress_data = {
            "progress": progress,
            "message": message,
            "meta": meta or {},
            "updated_at": timezone.now().isoformat(),
        }

        # Update Redis cache for real-time access
        try:
            cache_key = f"{PROGRESS_CACHE_PREFIX}{task_id}"
            cache.set(cache_key, progress_data, timeout=PROGRESS_CACHE_TIMEOUT)
        except Exception as e:
            logger.warning("Failed to update progress cache: %s", e)

        # Update database for persistence
        try:
            update_fields = {
                "progress": progress,
                "progress_message": message[:500] if message else "",
            }
            if meta:
                update_fields["meta"] = meta
            if progress > 0 and progress < 100:
                update_fields["status"] = TaskStatus.PROGRESS

            TaskResult.objects.filter(task_id=task_id).update(**update_fields)
        except Exception as e:
            logger.warning("Failed to update progress in database: %s", e)

    @classmethod
    def get_progress(cls, task_id: str) -> dict | None:
        """Get task progress from cache or database.

        Args:
            task_id: The Celery task ID

        Returns:
            Progress dictionary or None if not found
        """
        from core.tasks.models import TaskResult

        # Try cache first
        try:
            cache_key = f"{PROGRESS_CACHE_PREFIX}{task_id}"
            cached = cache.get(cache_key)
            if cached:
                return cached
        except Exception as e:
            logger.warning("Failed to get progress from cache: %s", e)

        # Fall back to database
        try:
            task = TaskResult.objects.filter(task_id=task_id).first()
            if task:
                return {
                    "progress": task.progress,
                    "message": task.progress_message,
                    "meta": task.meta,
                    "status": task.status,
                    "updated_at": task.completed_at or task.started_at,
                }
        except Exception as e:
            logger.warning("Failed to get progress from database: %s", e)

        return None

    @classmethod
    def get_task_status(cls, task_id: str) -> dict | None:
        """Get full task status including Celery state.

        Args:
            task_id: The Celery task ID

        Returns:
            Complete task status dictionary
        """
        from celery.result import AsyncResult

        from core.tasks.models import TaskResult

        result: dict[str, Any] = {
            "task_id": task_id,
            "celery_state": None,
            "database_status": None,
            "progress": 0,
            "message": "",
            "result": None,
            "error": None,
        }

        # Get Celery state
        try:
            async_result = AsyncResult(task_id)
            result["celery_state"] = async_result.state
            if async_result.state == "PROGRESS":
                info = async_result.info or {}
                result["progress"] = info.get("progress", 0)
                result["message"] = info.get("message", "")
            elif async_result.ready():
                if async_result.successful():
                    result["result"] = async_result.result
                else:
                    result["error"] = str(async_result.result)
        except Exception as e:
            logger.warning("Failed to get Celery state: %s", e)

        # Get database status
        try:
            task = TaskResult.objects.filter(task_id=task_id).first()
            if task:
                result["database_status"] = task.status
                result["progress"] = max(result["progress"], task.progress)
                result["message"] = result["message"] or task.progress_message
                result["result"] = result["result"] or task.result
                result["error"] = result["error"] or task.error
                result["started_at"] = task.started_at
                result["completed_at"] = task.completed_at
                result["duration"] = task.duration
        except Exception as e:
            logger.warning("Failed to get database status: %s", e)

        return result

    @classmethod
    def clear_progress(cls, task_id: str) -> None:
        """Clear task progress from cache.

        Args:
            task_id: The Celery task ID
        """
        try:
            cache_key = f"{PROGRESS_CACHE_PREFIX}{task_id}"
            cache.delete(cache_key)
        except Exception as e:
            logger.warning("Failed to clear progress cache: %s", e)

    @classmethod
    def get_active_tasks(cls) -> list[dict]:
        """Get all currently active (running) tasks.

        Returns:
            List of active task status dictionaries
        """
        from core.tasks.models import TaskResult, TaskStatus

        try:
            active_tasks = TaskResult.objects.filter(
                status__in=[TaskStatus.STARTED, TaskStatus.PROGRESS, TaskStatus.RETRY]
            ).order_by("-started_at")[:100]

            return [
                {
                    "task_id": task.task_id,
                    "name": task.name,
                    "status": task.status,
                    "progress": task.progress,
                    "message": task.progress_message,
                    "started_at": task.started_at,
                    "duration": task.duration,
                }
                for task in active_tasks
            ]
        except Exception as e:
            logger.warning("Failed to get active tasks: %s", e)
            return []

    @classmethod
    def get_recent_tasks(
        cls,
        limit: int = 50,
        status: str | None = None,
        task_name: str | None = None,
    ) -> list[dict]:
        """Get recent task results with optional filtering.

        Args:
            limit: Maximum number of results
            status: Optional status filter
            task_name: Optional task name filter

        Returns:
            List of task result dictionaries
        """
        from core.tasks.models import TaskResult

        try:
            queryset = TaskResult.objects.all()

            if status:
                queryset = queryset.filter(status=status)
            if task_name:
                queryset = queryset.filter(name__icontains=task_name)

            tasks = queryset.order_by("-created_at")[:limit]

            return [
                {
                    "id": str(task.id),
                    "task_id": task.task_id,
                    "name": task.name,
                    "status": task.status,
                    "progress": task.progress,
                    "message": task.progress_message,
                    "result": task.result,
                    "error": task.error or None,
                    "created_at": task.created_at,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "duration": task.duration,
                }
                for task in tasks
            ]
        except Exception as e:
            logger.warning("Failed to get recent tasks: %s", e)
            return []

    @classmethod
    def get_task_stats(cls) -> dict:
        """Get task execution statistics.

        Returns:
            Dictionary with task statistics
        """
        from django.db.models import Avg, Count, Q

        from core.tasks.models import TaskResult, TaskStatus

        try:
            stats = TaskResult.objects.aggregate(
                total=Count("id"),
                pending=Count("id", filter=Q(status=TaskStatus.PENDING)),
                running=Count(
                    "id",
                    filter=Q(status__in=[TaskStatus.STARTED, TaskStatus.PROGRESS]),
                ),
                success=Count("id", filter=Q(status=TaskStatus.SUCCESS)),
                failure=Count("id", filter=Q(status=TaskStatus.FAILURE)),
                retry=Count("id", filter=Q(status=TaskStatus.RETRY)),
            )

            # Calculate average duration for completed tasks
            completed_tasks = TaskResult.objects.filter(
                status__in=[TaskStatus.SUCCESS, TaskStatus.FAILURE],
                started_at__isnull=False,
                completed_at__isnull=False,
            )

            # Use raw query for duration calculation
            from django.db.models import ExpressionWrapper, F
            from django.db.models.fields import DurationField

            duration_stats = completed_tasks.annotate(
                task_duration=ExpressionWrapper(
                    F("completed_at") - F("started_at"),
                    output_field=DurationField(),
                )
            ).aggregate(avg_duration=Avg("task_duration"))

            avg_duration = duration_stats.get("avg_duration")
            stats["avg_duration_seconds"] = (
                avg_duration.total_seconds() if avg_duration else None
            )

            # Success rate
            completed = stats["success"] + stats["failure"]
            stats["success_rate"] = (
                (stats["success"] / completed * 100) if completed > 0 else 0
            )

            return stats
        except Exception as e:
            logger.warning("Failed to get task stats: %s", e)
            return {}
