"""Pluggable task queue abstraction layer.

Supports multiple backends via the TASK_BACKEND environment variable:
- celery (default): Full-featured distributed task queue
- huey: Lightweight alternative with Redis/SQLite backends
- django_q: Multiprocessing task queue with Django admin integration
- django_rq: Simple Redis Queue wrapper for Django

Usage:
    from api.tasks import shared_task

    @shared_task
    def my_task(arg1, arg2):
        ...

Existing Celery tasks continue to work unchanged when TASK_BACKEND=celery.
"""

from api.tasks.loader import get_task_decorator

shared_task = get_task_decorator()

__all__ = ["shared_task"]
