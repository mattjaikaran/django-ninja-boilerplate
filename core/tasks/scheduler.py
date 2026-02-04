"""Periodic task management utilities.

This module provides utilities for managing Celery Beat periodic tasks
through the database using django-celery-beat.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)


class PeriodicTaskManager:
    """Manager class for handling periodic task operations.

    Provides CRUD operations for periodic tasks stored in the database
    via django-celery-beat.
    """

    @classmethod
    def list_periodic_tasks(
        cls,
        enabled_only: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        """List all periodic tasks.

        Args:
            enabled_only: If True, only return enabled tasks
            limit: Maximum number of tasks to return

        Returns:
            List of periodic task dictionaries
        """
        try:
            from django_celery_beat.models import PeriodicTask

            queryset = PeriodicTask.objects.select_related(
                "interval",
                "crontab",
                "clocked",
            )

            if enabled_only:
                queryset = queryset.filter(enabled=True)

            tasks = queryset.order_by("name")[:limit]

            return [cls._task_to_dict(task) for task in tasks]
        except ImportError:
            logger.warning("django-celery-beat not installed")
            return []
        except Exception as e:
            logger.error("Failed to list periodic tasks: %s", e)
            return []

    @classmethod
    def get_periodic_task(cls, task_id: int) -> dict | None:
        """Get a specific periodic task by ID.

        Args:
            task_id: The periodic task ID

        Returns:
            Task dictionary or None if not found
        """
        try:
            from django_celery_beat.models import PeriodicTask

            task = PeriodicTask.objects.select_related(
                "interval",
                "crontab",
                "clocked",
            ).get(id=task_id)

            return cls._task_to_dict(task)
        except ImportError:
            logger.warning("django-celery-beat not installed")
            return None
        except Exception as e:
            logger.error("Failed to get periodic task %s: %s", task_id, e)
            return None

    @classmethod
    def create_interval_task(
        cls,
        name: str,
        task: str,
        every: int,
        period: str = "seconds",
        args: list | None = None,
        kwargs: dict | None = None,
        enabled: bool = True,
        one_off: bool = False,
        start_time: datetime | None = None,
        expires: datetime | None = None,
        description: str = "",
    ) -> dict | None:
        """Create an interval-based periodic task.

        Args:
            name: Unique name for the task
            task: Task path (e.g., 'core.tasks.cleanup_expired_otps')
            every: Number of periods between executions
            period: Period type ('seconds', 'minutes', 'hours', 'days')
            args: Positional arguments for the task
            kwargs: Keyword arguments for the task
            enabled: Whether the task is enabled
            one_off: If True, run only once then disable
            start_time: When to start running the task
            expires: When the task expires
            description: Task description

        Returns:
            Created task dictionary or None on failure
        """
        try:
            from django_celery_beat.models import IntervalSchedule, PeriodicTask

            # Create or get interval schedule
            period_mapping = {
                "seconds": IntervalSchedule.SECONDS,
                "minutes": IntervalSchedule.MINUTES,
                "hours": IntervalSchedule.HOURS,
                "days": IntervalSchedule.DAYS,
            }

            interval, _ = IntervalSchedule.objects.get_or_create(
                every=every,
                period=period_mapping.get(period, IntervalSchedule.SECONDS),
            )

            # Create periodic task
            periodic_task = PeriodicTask.objects.create(
                name=name,
                task=task,
                interval=interval,
                args=json.dumps(args or []),
                kwargs=json.dumps(kwargs or {}),
                enabled=enabled,
                one_off=one_off,
                start_time=start_time,
                expires=expires,
                description=description,
            )

            logger.info("Created interval task: %s", name)
            return cls._task_to_dict(periodic_task)

        except ImportError:
            logger.warning("django-celery-beat not installed")
            return None
        except Exception as e:
            logger.error("Failed to create interval task: %s", e)
            return None

    @classmethod
    def create_crontab_task(
        cls,
        name: str,
        task: str,
        minute: str = "*",
        hour: str = "*",
        day_of_week: str = "*",
        day_of_month: str = "*",
        month_of_year: str = "*",
        args: list | None = None,
        kwargs: dict | None = None,
        enabled: bool = True,
        one_off: bool = False,
        start_time: datetime | None = None,
        expires: datetime | None = None,
        description: str = "",
    ) -> dict | None:
        """Create a crontab-based periodic task.

        Args:
            name: Unique name for the task
            task: Task path (e.g., 'core.tasks.cleanup_expired_otps')
            minute: Minute field (0-59, *, */n)
            hour: Hour field (0-23, *, */n)
            day_of_week: Day of week (0-6, *, mon-sun)
            day_of_month: Day of month (1-31, *, */n)
            month_of_year: Month (1-12, *, */n)
            args: Positional arguments for the task
            kwargs: Keyword arguments for the task
            enabled: Whether the task is enabled
            one_off: If True, run only once then disable
            start_time: When to start running the task
            expires: When the task expires
            description: Task description

        Returns:
            Created task dictionary or None on failure
        """
        try:
            from django_celery_beat.models import CrontabSchedule, PeriodicTask

            # Create or get crontab schedule
            crontab, _ = CrontabSchedule.objects.get_or_create(
                minute=minute,
                hour=hour,
                day_of_week=day_of_week,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
            )

            # Create periodic task
            periodic_task = PeriodicTask.objects.create(
                name=name,
                task=task,
                crontab=crontab,
                args=json.dumps(args or []),
                kwargs=json.dumps(kwargs or {}),
                enabled=enabled,
                one_off=one_off,
                start_time=start_time,
                expires=expires,
                description=description,
            )

            logger.info("Created crontab task: %s", name)
            return cls._task_to_dict(periodic_task)

        except ImportError:
            logger.warning("django-celery-beat not installed")
            return None
        except Exception as e:
            logger.error("Failed to create crontab task: %s", e)
            return None

    @classmethod
    def update_periodic_task(
        cls,
        task_id: int,
        **updates: Any,
    ) -> dict | None:
        """Update an existing periodic task.

        Args:
            task_id: The periodic task ID
            **updates: Fields to update

        Returns:
            Updated task dictionary or None on failure
        """
        try:
            from django_celery_beat.models import PeriodicTask

            task = PeriodicTask.objects.get(id=task_id)

            # Handle JSON fields
            if "args" in updates:
                updates["args"] = json.dumps(updates["args"])
            if "kwargs" in updates:
                updates["kwargs"] = json.dumps(updates["kwargs"])

            for field, value in updates.items():
                if hasattr(task, field):
                    setattr(task, field, value)

            task.save()

            logger.info("Updated periodic task: %s", task.name)
            return cls._task_to_dict(task)

        except ImportError:
            logger.warning("django-celery-beat not installed")
            return None
        except Exception as e:
            logger.error("Failed to update periodic task %s: %s", task_id, e)
            return None

    @classmethod
    def delete_periodic_task(cls, task_id: int) -> bool:
        """Delete a periodic task.

        Args:
            task_id: The periodic task ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            from django_celery_beat.models import PeriodicTask

            task = PeriodicTask.objects.get(id=task_id)
            name = task.name
            task.delete()

            logger.info("Deleted periodic task: %s", name)
            return True

        except ImportError:
            logger.warning("django-celery-beat not installed")
            return False
        except Exception as e:
            logger.error("Failed to delete periodic task %s: %s", task_id, e)
            return False

    @classmethod
    def toggle_periodic_task(cls, task_id: int, enabled: bool | None = None) -> dict | None:
        """Toggle a periodic task's enabled status.

        Args:
            task_id: The periodic task ID
            enabled: If provided, set to this value. Otherwise toggle.

        Returns:
            Updated task dictionary or None on failure
        """
        try:
            from django_celery_beat.models import PeriodicTask

            task = PeriodicTask.objects.get(id=task_id)

            if enabled is None:
                task.enabled = not task.enabled
            else:
                task.enabled = enabled

            task.save(update_fields=["enabled"])

            logger.info(
                "Toggled periodic task %s: enabled=%s",
                task.name,
                task.enabled,
            )
            return cls._task_to_dict(task)

        except ImportError:
            logger.warning("django-celery-beat not installed")
            return None
        except Exception as e:
            logger.error("Failed to toggle periodic task %s: %s", task_id, e)
            return None

    @classmethod
    def run_periodic_task_now(cls, task_id: int) -> str | None:
        """Manually trigger a periodic task to run immediately.

        Args:
            task_id: The periodic task ID

        Returns:
            The new task ID or None on failure
        """
        try:
            from celery import current_app
            from django_celery_beat.models import PeriodicTask

            task = PeriodicTask.objects.get(id=task_id)

            # Parse args and kwargs
            args = json.loads(task.args) if task.args else []
            kwargs = json.loads(task.kwargs) if task.kwargs else {}

            # Send task
            result = current_app.send_task(task.task, args=args, kwargs=kwargs)

            logger.info(
                "Manually triggered periodic task %s: new_task_id=%s",
                task.name,
                result.id,
            )
            return result.id

        except ImportError:
            logger.warning("django-celery-beat not installed")
            return None
        except Exception as e:
            logger.error("Failed to run periodic task %s: %s", task_id, e)
            return None

    @classmethod
    def get_scheduler_stats(cls) -> dict:
        """Get statistics about the scheduler.

        Returns:
            Dictionary with scheduler statistics
        """
        try:
            from django_celery_beat.models import PeriodicTask

            stats = {
                "total_tasks": PeriodicTask.objects.count(),
                "enabled_tasks": PeriodicTask.objects.filter(enabled=True).count(),
                "disabled_tasks": PeriodicTask.objects.filter(enabled=False).count(),
                "one_off_tasks": PeriodicTask.objects.filter(one_off=True).count(),
            }

            # Get tasks by schedule type
            stats["interval_tasks"] = PeriodicTask.objects.filter(
                interval__isnull=False
            ).count()
            stats["crontab_tasks"] = PeriodicTask.objects.filter(
                crontab__isnull=False
            ).count()
            stats["clocked_tasks"] = PeriodicTask.objects.filter(
                clocked__isnull=False
            ).count()

            # Get recently run tasks
            recent_cutoff = timezone.now() - timedelta(hours=24)
            stats["tasks_run_24h"] = PeriodicTask.objects.filter(
                last_run_at__gte=recent_cutoff
            ).count()

            return stats

        except ImportError:
            logger.warning("django-celery-beat not installed")
            return {}
        except Exception as e:
            logger.error("Failed to get scheduler stats: %s", e)
            return {}

    @classmethod
    def _task_to_dict(cls, task) -> dict:
        """Convert a PeriodicTask model to a dictionary.

        Args:
            task: PeriodicTask model instance

        Returns:
            Dictionary representation
        """
        schedule_type = "unknown"
        schedule_info = None

        if task.interval:
            schedule_type = "interval"
            schedule_info = {
                "every": task.interval.every,
                "period": task.interval.period,
            }
        elif task.crontab:
            schedule_type = "crontab"
            schedule_info = {
                "minute": task.crontab.minute,
                "hour": task.crontab.hour,
                "day_of_week": task.crontab.day_of_week,
                "day_of_month": task.crontab.day_of_month,
                "month_of_year": task.crontab.month_of_year,
            }
        elif task.clocked:
            schedule_type = "clocked"
            schedule_info = {
                "clocked_time": task.clocked.clocked_time.isoformat(),
            }

        return {
            "id": task.id,
            "name": task.name,
            "task": task.task,
            "enabled": task.enabled,
            "schedule_type": schedule_type,
            "schedule": schedule_info,
            "args": json.loads(task.args) if task.args else [],
            "kwargs": json.loads(task.kwargs) if task.kwargs else {},
            "one_off": task.one_off,
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "expires": task.expires.isoformat() if task.expires else None,
            "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
            "total_run_count": task.total_run_count,
            "description": task.description,
            "date_changed": task.date_changed.isoformat() if task.date_changed else None,
        }
