"""Task backend loader based on TASK_BACKEND setting."""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def get_task_decorator():
    """Return the appropriate task decorator for the configured backend.

    Returns a decorator that works like @shared_task regardless of backend.
    """
    backend = getattr(settings, "TASK_BACKEND", "celery")

    if backend == "huey":
        try:
            from huey.contrib.djhuey import task

            logger.info("Task backend: Huey")
            return task()
        except ImportError:
            logger.warning("Huey not installed, falling back to Celery")

    elif backend == "django_q":
        try:
            from api.tasks.backends.django_q_backend import django_q_task

            logger.info("Task backend: django-q2")
            return django_q_task
        except ImportError:
            logger.warning("django-q2 not installed, falling back to Celery")

    elif backend == "django_rq":
        try:
            from api.tasks.backends.django_rq_backend import rq_task

            logger.info("Task backend: django-rq")
            return rq_task
        except ImportError:
            logger.warning("django-rq not installed, falling back to Celery")

    from celery import shared_task

    logger.info("Task backend: Celery")
    return shared_task
