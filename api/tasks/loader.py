"""Load the task decorator selected by ``TASK_BACKEND``."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from importlib import import_module
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from api.tasks.contract import TaskHandle

BackendDecorator = Callable[..., TaskHandle]

_BACKENDS: dict[str, tuple[str, str, str]] = {
    "celery": (
        "api.tasks.backends.celery_backend",
        "celery_task",
        "celery",
    ),
    "huey": (
        "api.tasks.backends.huey_backend",
        "huey_backend_task",
        "huey",
    ),
    "django_q": (
        "api.tasks.backends.django_q_backend",
        "django_q_task",
        "django-q2",
    ),
    "django_rq": (
        "api.tasks.backends.django_rq_backend",
        "rq_task",
        "django-rq",
    ),
    "dramatiq": (
        "api.tasks.backends.dramatiq_backend",
        "dramatiq_task",
        "dramatiq[redis]",
    ),
}


def _load_backend() -> BackendDecorator:
    backend = getattr(settings, "TASK_BACKEND", "celery")
    try:
        module_name, attribute, package = _BACKENDS[backend]
    except KeyError as exc:
        choices = ", ".join(_BACKENDS)
        raise ImproperlyConfigured(
            f"Unknown TASK_BACKEND '{backend}'. Expected one of: {choices}."
        ) from exc

    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = exc.name or package
        raise ImproperlyConfigured(
            f"TASK_BACKEND='{backend}' requires the '{package}' package. "
            f"Missing import: '{missing}'. Install the "
            f"'{backend.replace('_', '-')}' optional extra."
        ) from exc
    return getattr(module, attribute)


def get_task_decorator():
    """Return a ``shared_task``-compatible decorator for the configured backend."""
    backend_decorator = _load_backend()

    def decorate(
        func=None,
        *,
        name: str | None = None,
        bind: bool = False,
        max_retries: int = 3,
        **options: Any,
    ):
        kwargs = {
            "name": name,
            "bind": bind,
            "max_retries": max_retries,
            **options,
        }
        if func is None:
            return partial(backend_decorator, **kwargs)
        return backend_decorator(func, **kwargs)

    return decorate


__all__ = ["get_task_decorator"]
