"""Celery configuration for the Django Ninja Boilerplate.

This module sets up Celery for background task processing with Redis as broker.
Includes multi-queue routing, signal-based monitoring, and retry helpers.

Usage:
    Start worker: celery -A api worker -l info
    Start worker (specific queue): celery -A api worker -Q emails -l info
    Start beat: celery -A api beat -l info
    Start flower: celery -A api flower
"""

import logging
import os
import random
import time

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

logger = logging.getLogger(__name__)

app = Celery("api")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


# =============================================================================
# Task Queues
# =============================================================================

app.conf.task_queues = {
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
    "emails": {
        "exchange": "emails",
        "routing_key": "emails",
    },
    "bulk": {
        "exchange": "bulk",
        "routing_key": "bulk",
    },
}

app.conf.task_default_queue = "default"

# Task routing
app.conf.task_routes = {
    # Route email tasks to emails queue
    "core.tasks.send_*_email": {"queue": "emails"},
    "core.tasks.send_email_*": {"queue": "emails"},
    "*send_email*": {"queue": "emails"},
    # Route bulk/heavy tasks to bulk queue
    "*bulk*": {"queue": "bulk"},
    "*cleanup*": {"queue": "bulk"},
    "*export*": {"queue": "bulk"},
    "*import*": {"queue": "bulk"},
}

# =============================================================================
# Per-Task Annotations (rate limits, timeouts)
# =============================================================================

app.conf.task_annotations = {
    "*": {
        "rate_limit": "100/m",  # Default: 100 tasks per minute per worker
    },
    "*send_email*": {
        "rate_limit": "30/m",  # Email: 30 per minute to avoid spam triggers
        "time_limit": 60,
    },
    "*bulk*": {
        "rate_limit": "5/m",
        "time_limit": 600,  # 10 minute timeout for bulk ops
    },
}

# =============================================================================
# Signal Handlers (Monitoring)
# =============================================================================

# Store for tracking task start times
_task_start_times: dict[str, float] = {}


@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Log when a task starts executing."""
    _task_start_times[task_id] = time.time()
    logger.info("Task started: %s [%s]", task.name, task_id)


@task_postrun.connect
def task_postrun_handler(task_id, task, retval, state, *args, **kwargs):
    """Log when a task finishes with duration."""
    start = _task_start_times.pop(task_id, None)
    duration = f"{time.time() - start:.2f}s" if start else "unknown"
    logger.info("Task completed: %s [%s] state=%s duration=%s", task.name, task_id, state, duration)


@task_failure.connect
def task_failure_handler(task_id, exception, traceback, sender, *args, **kwargs):
    """Log task failures for alerting."""
    logger.error(
        "Task failed: %s [%s] error=%s",
        sender.name,
        task_id,
        str(exception),
    )


# =============================================================================
# Retry Helpers
# =============================================================================


def exponential_backoff(retries: int, base: int = 2, max_delay: int = 600) -> int:
    """Calculate exponential backoff delay with jitter.

    Args:
        retries: Current retry count
        base: Base multiplier in seconds
        max_delay: Maximum delay in seconds (default 10 minutes)

    Returns:
        Delay in seconds with jitter applied
    """
    delay = min(base * (2**retries), max_delay)
    # Add jitter (up to 25% of delay)
    jitter = random.uniform(0, delay * 0.25)  # noqa: S311
    return int(delay + jitter)


# =============================================================================
# Beat Schedule (Periodic Tasks)
# =============================================================================

# Note: When using django_celery_beat, periodic tasks are managed in the database.
# This schedule provides sensible defaults that can be overridden via the admin.
#
# from celery.schedules import crontab
#
# app.conf.beat_schedule = {
#     "cleanup-expired-tokens-daily": {
#         "task": "core.tasks.cleanup_expired_tokens",
#         "schedule": crontab(hour=2, minute=0),
#     },
#     "send-daily-digest": {
#         "task": "core.tasks.send_daily_digest",
#         "schedule": crontab(hour=8, minute=0),
#     },
#     "cleanup-old-audit-logs-weekly": {
#         "task": "core.tasks.cleanup_old_audit_logs",
#         "schedule": crontab(hour=3, minute=0, day_of_week=0),
#     },
# }


# =============================================================================
# Debug Task
# =============================================================================


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task that prints request info."""
    print(f"Request: {self.request!r}")
