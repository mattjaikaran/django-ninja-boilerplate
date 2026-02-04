"""Enhanced base task class with progress tracking support.

This module provides an enhanced Celery task base class that includes:
- Automatic progress tracking
- Task state persistence to database
- Error handling with dead letter queue support
- Retry logic with exponential backoff
"""

import logging
from typing import Any

from celery import Task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ProgressTask(Task):
    """Enhanced Celery task with progress tracking capabilities.

    This task class provides:
    - Automatic task result persistence to database
    - Progress updates that can be tracked via API
    - Automatic error handling and DLQ support
    - Retry with exponential backoff

    Usage:
        from api.celery import app
        from core.tasks.base import ProgressTask

        @app.task(base=ProgressTask, bind=True)
        def my_task(self, arg1, arg2):
            self.update_progress(0, "Starting task...")
            # Do work
            self.update_progress(50, "Halfway done...")
            # More work
            self.update_progress(100, "Complete!")
            return {"result": "success"}
    """

    # Default retry configuration
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max backoff
    retry_jitter = True
    max_retries = 3

    # Track progress in database
    track_started = True
    track_progress = True

    def __init__(self):
        """Initialize the task."""
        super().__init__()
        self._progress = 0
        self._progress_message = ""

    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        """Called before task execution starts.

        Creates or updates the TaskResult record in the database.
        """
        from core.tasks.models import TaskResult, TaskStatus

        try:
            with transaction.atomic():
                TaskResult.objects.update_or_create(
                    task_id=task_id,
                    defaults={
                        "name": self.name,
                        "status": TaskStatus.STARTED,
                        "progress": 0,
                        "args": list(args) if args else [],
                        "kwargs": kwargs or {},
                        "started_at": timezone.now(),
                    },
                )
            logger.debug("Task %s started: %s", self.name, task_id)
        except Exception as e:
            logger.warning("Failed to record task start: %s", e)

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """Called when task completes successfully.

        Updates the TaskResult record with success status and result.
        """
        from core.tasks.models import TaskResult, TaskStatus

        try:
            TaskResult.objects.filter(task_id=task_id).update(
                status=TaskStatus.SUCCESS,
                progress=100,
                result=retval if isinstance(retval, dict) else {"value": retval},
                completed_at=timezone.now(),
            )
            logger.debug("Task %s succeeded: %s", self.name, task_id)
        except Exception as e:
            logger.warning("Failed to record task success: %s", e)

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """Called when task fails.

        Updates the TaskResult record with failure status and error details.
        Also adds the task to the dead letter queue if max retries exceeded.
        """
        from core.tasks.dlq import DeadLetterQueue
        from core.tasks.models import TaskResult, TaskStatus

        try:
            TaskResult.objects.filter(task_id=task_id).update(
                status=TaskStatus.FAILURE,
                error=str(exc),
                traceback=str(einfo) if einfo else None,
                completed_at=timezone.now(),
            )

            # Add to dead letter queue if max retries exceeded
            if self.request.retries >= self.max_retries:
                DeadLetterQueue.add_failed_task(
                    task_id=task_id,
                    task_name=self.name,
                    args=args,
                    kwargs=kwargs,
                    exception=exc,
                    traceback=str(einfo) if einfo else None,
                )

            logger.error(
                "Task %s failed: %s - %s",
                self.name,
                task_id,
                exc,
            )
        except Exception as e:
            logger.warning("Failed to record task failure: %s", e)

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """Called when task is being retried.

        Updates the TaskResult record with retry status.
        """
        from core.tasks.models import TaskResult, TaskStatus

        try:
            TaskResult.objects.filter(task_id=task_id).update(
                status=TaskStatus.RETRY,
                error=f"Retry {self.request.retries}/{self.max_retries}: {exc}",
            )
            logger.info(
                "Task %s retrying (%d/%d): %s",
                self.name,
                self.request.retries,
                self.max_retries,
                task_id,
            )
        except Exception as e:
            logger.warning("Failed to record task retry: %s", e)

    def update_progress(
        self,
        progress: int,
        message: str = "",
        meta: dict | None = None,
    ) -> None:
        """Update task progress.

        Args:
            progress: Progress percentage (0-100)
            message: Optional progress message
            meta: Optional metadata dictionary
        """
        from core.tasks.progress import TaskProgressTracker

        self._progress = min(100, max(0, progress))
        self._progress_message = message

        # Update Celery state
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": self._progress,
                "message": message,
                "meta": meta or {},
            },
        )

        # Update database record
        if self.request.id:
            TaskProgressTracker.update_progress(
                task_id=self.request.id,
                progress=self._progress,
                message=message,
                meta=meta,
            )

    def get_progress(self) -> dict:
        """Get current task progress.

        Returns:
            Dictionary with progress, message, and metadata
        """
        return {
            "progress": self._progress,
            "message": self._progress_message,
        }


class RetryableTask(ProgressTask):
    """Task with configurable retry behavior.

    Usage:
        @app.task(base=RetryableTask, bind=True, max_retries=5)
        def my_retryable_task(self, data):
            try:
                # risky operation
                pass
            except SomeException as e:
                raise self.retry(exc=e, countdown=60)
    """

    # More aggressive retry defaults
    max_retries = 5
    retry_backoff = True
    retry_backoff_max = 1800  # 30 minutes max backoff
    default_retry_delay = 60  # 1 minute initial delay


class LongRunningTask(ProgressTask):
    """Task optimized for long-running operations.

    Features:
    - Extended time limits
    - Reduced retry attempts
    - Longer backoff periods
    """

    # Extended time limits
    soft_time_limit = 3600  # 1 hour soft limit
    time_limit = 3900  # 1 hour 5 minutes hard limit

    # Reduced retries for long tasks
    max_retries = 2
    retry_backoff_max = 3600  # 1 hour max backoff


class CriticalTask(ProgressTask):
    """Task for critical operations that must complete.

    Features:
    - No automatic retries (manual control)
    - Immediate DLQ on failure
    - Detailed logging
    """

    autoretry_for = ()  # No automatic retries
    max_retries = 0

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        """Immediately add to DLQ on failure."""
        from core.tasks.dlq import DeadLetterQueue
        from core.tasks.models import TaskResult, TaskStatus

        try:
            TaskResult.objects.filter(task_id=task_id).update(
                status=TaskStatus.FAILURE,
                error=str(exc),
                traceback=str(einfo) if einfo else None,
                completed_at=timezone.now(),
            )

            # Always add critical tasks to DLQ
            DeadLetterQueue.add_failed_task(
                task_id=task_id,
                task_name=self.name,
                args=args,
                kwargs=kwargs,
                exception=exc,
                traceback=str(einfo) if einfo else None,
                priority="high",
            )

            logger.critical(
                "Critical task %s failed: %s - %s",
                self.name,
                task_id,
                exc,
            )
        except Exception as e:
            logger.error("Failed to handle critical task failure: %s", e)
