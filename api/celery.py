"""Celery configuration for the Django Ninja Boilerplate.

This module sets up Celery for background task processing with Redis as broker.

Usage:
    Start worker: celery -A api worker -l info
    Start beat: celery -A api beat -l info
    Start flower: celery -A api flower

Example task:
    from api.celery import app

    @app.task
    def my_task(arg):
        return arg * 2
"""

import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

app = Celery("api")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task that prints request info."""
    print(f"Request: {self.request!r}")


# =============================================================================
# Common Celery Task Decorators
# =============================================================================


def shared_task(*args, **kwargs):
    """Decorator for shared tasks that can be used across apps.

    Example:
        @shared_task
        def send_email(to, subject, body):
            # Send email logic
            pass
    """
    return app.task(*args, **kwargs)


# =============================================================================
# Task Routing Configuration
# =============================================================================

# Define task queues for different priorities
app.conf.task_queues = {
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
    "high_priority": {
        "exchange": "high_priority",
        "routing_key": "high_priority",
    },
    "low_priority": {
        "exchange": "low_priority",
        "routing_key": "low_priority",
    },
}

# Default queue
app.conf.task_default_queue = "default"

# Task routing
app.conf.task_routes = {
    # Route email tasks to high priority queue
    "core.tasks.send_email_*": {"queue": "high_priority"},
    # Route cleanup tasks to low priority queue
    "*cleanup*": {"queue": "low_priority"},
}

# =============================================================================
# Beat Schedule (Periodic Tasks)
# =============================================================================

# Note: When using django_celery_beat, periodic tasks are managed in the database.
# This is just for reference of common patterns.
#
# app.conf.beat_schedule = {
#     'cleanup-expired-tokens-daily': {
#         'task': 'core.tasks.cleanup_expired_tokens',
#         'schedule': crontab(hour=0, minute=0),  # Run at midnight
#     },
#     'send-daily-digest': {
#         'task': 'core.tasks.send_daily_digest',
#         'schedule': crontab(hour=8, minute=0),  # Run at 8 AM
#     },
# }
