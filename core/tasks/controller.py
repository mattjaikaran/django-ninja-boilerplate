"""API controller for task management.

This module provides API endpoints for:
- Task status and progress tracking
- Periodic task management (CRUD)
- Dead letter queue operations
- Task statistics and monitoring
"""

import logging

from celery import current_app
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import handle_exceptions, log_api_call
from core.tasks.dlq import DeadLetterQueue
from core.tasks.progress import TaskProgressTracker
from core.tasks.scheduler import PeriodicTaskManager
from core.tasks.schemas import (
    CleanupResponseSchema,
    CreateCrontabTaskSchema,
    CreateIntervalTaskSchema,
    DLQBulkResolveSchema,
    DLQBulkRetryResponseSchema,
    DLQBulkRetrySchema,
    DLQEntrySchema,
    DLQListSchema,
    DLQResolveSchema,
    DLQRetryResponseSchema,
    DLQStatsSchema,
    PeriodicTaskSchema,
    SchedulerStatsSchema,
    TaskActionResponseSchema,
    TaskStatsSchema,
    TaskStatusSchema,
    UpdatePeriodicTaskSchema,
)

logger = logging.getLogger(__name__)


@api_controller("/tasks", tags=["Tasks"])
class TaskController:
    """Controller for task status and monitoring endpoints."""

    # =========================================================================
    # Task Status Endpoints
    # =========================================================================

    @http_get("/{task_id}/status", response={200: TaskStatusSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_task_status(self, task_id: str):
        """Get the status of a specific task.

        Returns both Celery state and database status for comprehensive
        task tracking.
        """
        status = TaskProgressTracker.get_task_status(task_id)
        if not status:
            return 404, {"error": "Task not found"}
        return 200, status

    @http_get("/{task_id}/progress", response={200: dict, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_task_progress(self, task_id: str):
        """Get the progress of a specific task.

        Returns real-time progress information from cache or database.
        """
        progress = TaskProgressTracker.get_progress(task_id)
        if not progress:
            return 404, {"error": "Task progress not found"}
        return 200, progress

    @http_post("/{task_id}/revoke", response={200: TaskActionResponseSchema})
    @handle_exceptions()
    @log_api_call()
    def revoke_task(self, task_id: str, terminate: bool = False):
        """Revoke (cancel) a running task.

        Args:
            task_id: The Celery task ID
            terminate: If True, forcefully terminate the task
        """
        from core.tasks.models import TaskResult

        try:
            current_app.control.revoke(task_id, terminate=terminate)

            # Update database record
            TaskResult.objects.filter(task_id=task_id).update(
                status="revoked",
            )

            return 200, {
                "success": True,
                "message": f"Task {task_id} revoked",
                "task_id": task_id,
            }
        except Exception as e:
            logger.error("Failed to revoke task %s: %s", task_id, e)
            return 200, {
                "success": False,
                "message": str(e),
                "task_id": task_id,
            }

    @http_get("/active", response={200: list[dict]})
    @handle_exceptions()
    @log_api_call()
    def list_active_tasks(self):
        """List all currently active (running) tasks."""
        return 200, TaskProgressTracker.get_active_tasks()

    @http_get("/recent", response={200: list[dict]})
    @handle_exceptions()
    @log_api_call()
    def list_recent_tasks(
        self,
        limit: int = 50,
        status: str | None = None,
        task_name: str | None = None,
    ):
        """List recent task results with optional filtering.

        Args:
            limit: Maximum number of results (default 50)
            status: Filter by status (pending, started, success, failure)
            task_name: Filter by task name (partial match)
        """
        return 200, TaskProgressTracker.get_recent_tasks(
            limit=limit,
            status=status,
            task_name=task_name,
        )

    @http_get("/stats", response={200: TaskStatsSchema})
    @handle_exceptions()
    @log_api_call()
    def get_task_stats(self):
        """Get task execution statistics."""
        return 200, TaskProgressTracker.get_task_stats()

    @http_post("/cleanup", response={200: CleanupResponseSchema})
    @handle_exceptions()
    @log_api_call()
    def cleanup_old_tasks(self, days: int = 30):
        """Clean up old task results.

        Args:
            days: Delete results older than this many days
        """
        from core.tasks.models import TaskResult

        deleted = TaskResult.cleanup_old_results(days=days)

        return 200, {
            "success": True,
            "deleted": deleted,
            "message": f"Deleted {deleted} task results older than {days} days",
        }


@api_controller("/tasks/scheduler", tags=["Task Scheduler"])
class TaskSchedulerController:
    """Controller for periodic task management endpoints."""

    # =========================================================================
    # Periodic Task Endpoints
    # =========================================================================

    @http_get("/", response={200: list[PeriodicTaskSchema]})
    @handle_exceptions()
    @log_api_call()
    def list_periodic_tasks(self, enabled_only: bool = False):
        """List all periodic tasks.

        Args:
            enabled_only: If True, only return enabled tasks
        """
        tasks = PeriodicTaskManager.list_periodic_tasks(enabled_only=enabled_only)
        return 200, tasks

    @http_get("/{task_id}", response={200: PeriodicTaskSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_periodic_task(self, task_id: int):
        """Get a specific periodic task by ID."""
        task = PeriodicTaskManager.get_periodic_task(task_id)
        if not task:
            return 404, {"error": "Periodic task not found"}
        return 200, task

    @http_post("/interval", response={201: PeriodicTaskSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_interval_task(self, data: CreateIntervalTaskSchema):
        """Create a new interval-based periodic task.

        Creates a task that runs every N seconds/minutes/hours/days.
        """
        task = PeriodicTaskManager.create_interval_task(
            name=data.name,
            task=data.task,
            every=data.every,
            period=data.period,
            args=data.args,
            kwargs=data.kwargs,
            enabled=data.enabled,
            one_off=data.one_off,
            start_time=data.start_time,
            expires=data.expires,
            description=data.description,
        )

        if not task:
            return 400, {"error": "Failed to create periodic task"}

        return 201, task

    @http_post("/crontab", response={201: PeriodicTaskSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_crontab_task(self, data: CreateCrontabTaskSchema):
        """Create a new crontab-based periodic task.

        Creates a task that runs on a cron schedule.
        """
        task = PeriodicTaskManager.create_crontab_task(
            name=data.name,
            task=data.task,
            minute=data.minute,
            hour=data.hour,
            day_of_week=data.day_of_week,
            day_of_month=data.day_of_month,
            month_of_year=data.month_of_year,
            args=data.args,
            kwargs=data.kwargs,
            enabled=data.enabled,
            one_off=data.one_off,
            start_time=data.start_time,
            expires=data.expires,
            description=data.description,
        )

        if not task:
            return 400, {"error": "Failed to create periodic task"}

        return 201, task

    @http_put("/{task_id}", response={200: PeriodicTaskSchema, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_periodic_task(self, task_id: int, data: UpdatePeriodicTaskSchema):
        """Update an existing periodic task."""
        # Filter out None values
        updates = {k: v for k, v in data.dict().items() if v is not None}

        if not updates:
            return 400, {"error": "No updates provided"}

        task = PeriodicTaskManager.update_periodic_task(task_id, **updates)

        if not task:
            return 404, {"error": "Periodic task not found"}

        return 200, task

    @http_delete("/{task_id}", response={200: dict, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_periodic_task(self, task_id: int):
        """Delete a periodic task."""
        success = PeriodicTaskManager.delete_periodic_task(task_id)

        if not success:
            return 404, {"error": "Periodic task not found"}

        return 200, {"success": True, "message": "Periodic task deleted"}

    @http_post("/{task_id}/toggle", response={200: PeriodicTaskSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def toggle_periodic_task(self, task_id: int, enabled: bool | None = None):
        """Toggle a periodic task's enabled status.

        Args:
            task_id: The periodic task ID
            enabled: If provided, set to this value. Otherwise toggle.
        """
        task = PeriodicTaskManager.toggle_periodic_task(task_id, enabled=enabled)

        if not task:
            return 404, {"error": "Periodic task not found"}

        return 200, task

    @http_post("/{task_id}/run", response={200: TaskActionResponseSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def run_periodic_task_now(self, task_id: int):
        """Manually trigger a periodic task to run immediately."""
        new_task_id = PeriodicTaskManager.run_periodic_task_now(task_id)

        if not new_task_id:
            return 404, {"error": "Periodic task not found or failed to trigger"}

        return 200, {
            "success": True,
            "message": "Task triggered successfully",
            "task_id": new_task_id,
        }

    @http_get("/stats", response={200: SchedulerStatsSchema})
    @handle_exceptions()
    @log_api_call()
    def get_scheduler_stats(self):
        """Get scheduler statistics."""
        return 200, PeriodicTaskManager.get_scheduler_stats()


@api_controller("/tasks/dlq", tags=["Dead Letter Queue"])
class DeadLetterQueueController:
    """Controller for dead letter queue operations."""

    # =========================================================================
    # DLQ Endpoints
    # =========================================================================

    @http_get("/", response={200: DLQListSchema})
    @handle_exceptions()
    @log_api_call()
    def list_dlq_entries(
        self,
        include_resolved: bool = False,
        priority: str | None = None,
        task_name: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        """List dead letter queue entries.

        Args:
            include_resolved: Include resolved entries
            priority: Filter by priority (low, normal, high, critical)
            task_name: Filter by task name (partial match)
            limit: Maximum number of entries
            offset: Pagination offset
        """
        entries = DeadLetterQueue.list_entries(
            include_resolved=include_resolved,
            priority=priority,
            task_name=task_name,
            limit=limit,
            offset=offset,
        )

        # Get total count
        from core.tasks.models import DeadLetterQueueEntry

        queryset = DeadLetterQueueEntry.objects.all()
        if not include_resolved:
            queryset = queryset.filter(is_resolved=False)
        if priority:
            queryset = queryset.filter(priority=priority)
        if task_name:
            queryset = queryset.filter(task_name__icontains=task_name)

        return 200, {
            "items": entries,
            "total": queryset.count(),
        }

    @http_get("/{entry_id}", response={200: DLQEntrySchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_dlq_entry(self, entry_id: str):
        """Get a specific DLQ entry."""
        entry = DeadLetterQueue.get_entry(entry_id)

        if not entry:
            return 404, {"error": "DLQ entry not found"}

        return 200, entry

    @http_post("/{entry_id}/retry", response={200: DLQRetryResponseSchema})
    @handle_exceptions()
    @log_api_call()
    def retry_dlq_entry(self, entry_id: str):
        """Retry a failed task from the DLQ."""
        new_task_id = DeadLetterQueue.retry_entry(entry_id)

        if new_task_id:
            return 200, {
                "success": True,
                "new_task_id": new_task_id,
                "message": "Task retried successfully",
            }
        return 200, {
            "success": False,
            "new_task_id": None,
            "message": "Failed to retry task. Entry may be resolved or exhausted retries.",
        }

    @http_post("/retry-all", response={200: DLQBulkRetryResponseSchema})
    @handle_exceptions()
    @log_api_call()
    def retry_all_pending(self, data: DLQBulkRetrySchema):
        """Retry all pending DLQ entries that can be retried."""
        results = DeadLetterQueue.retry_all_pending(
            task_name=data.task_name,
            priority=data.priority,
            limit=data.limit,
        )
        return 200, results

    @http_post("/{entry_id}/resolve", response={200: DLQEntrySchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def resolve_dlq_entry(self, entry_id: str, data: DLQResolveSchema):
        """Mark a DLQ entry as resolved."""
        entry = DeadLetterQueue.resolve_entry(entry_id, notes=data.notes)

        if not entry:
            return 404, {"error": "DLQ entry not found"}

        return 200, entry

    @http_post("/resolve-bulk", response={200: dict})
    @handle_exceptions()
    @log_api_call()
    def bulk_resolve_entries(self, data: DLQBulkResolveSchema):
        """Resolve multiple DLQ entries."""
        results = DeadLetterQueue.bulk_resolve(
            entry_ids=data.entry_ids,
            notes=data.notes,
        )
        return 200, results

    @http_delete("/{entry_id}", response={200: dict, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_dlq_entry(self, entry_id: str):
        """Permanently delete a DLQ entry."""
        success = DeadLetterQueue.delete_entry(entry_id)

        if not success:
            return 404, {"error": "DLQ entry not found"}

        return 200, {"success": True, "message": "DLQ entry deleted"}

    @http_get("/stats", response={200: DLQStatsSchema})
    @handle_exceptions()
    @log_api_call()
    def get_dlq_stats(self):
        """Get DLQ statistics."""
        return 200, DeadLetterQueue.get_stats()

    @http_post("/cleanup", response={200: CleanupResponseSchema})
    @handle_exceptions()
    @log_api_call()
    def cleanup_dlq(self, days: int = 30):
        """Clean up old resolved DLQ entries.

        Args:
            days: Delete resolved entries older than this many days
        """
        results = DeadLetterQueue.cleanup(days=days)

        if "error" in results:
            return 200, {
                "success": False,
                "deleted": 0,
                "message": results["error"],
            }

        return 200, {
            "success": True,
            "deleted": results["deleted"],
            "message": f"Deleted {results['deleted']} resolved DLQ entries older than {days} days",
        }
