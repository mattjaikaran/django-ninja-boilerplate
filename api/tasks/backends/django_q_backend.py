"""django-q2 adapter for the backend-neutral task contract."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone
from django_q.models import Schedule
from django_q.tasks import async_task, schedule

from api.tasks.contract import TaskHandle, execute_task, register_task, task_name


def _execute(
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    attempt: int,
) -> Any:
    return execute_task(name, args, kwargs, attempt)


def django_q_task(
    func,
    *,
    name: str | None = None,
    bind: bool = False,
    max_retries: int = 3,
    **options: Any,
) -> TaskHandle:
    """Wrap a function as a django-q2 task with the uniform contract."""
    if options:
        unknown = ", ".join(sorted(options))
        raise TypeError(f"Unsupported django-q2 task options: {unknown}")

    resolved_name = task_name(func, name)

    def enqueue(
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        countdown: float,
        attempt: int,
    ) -> Any:
        call_args = (resolved_name, args, kwargs, attempt)
        if countdown > 0:
            return schedule(
                _execute,
                *call_args,
                name=resolved_name,
                schedule_type=Schedule.ONCE,
                next_run=timezone.now() + timedelta(seconds=countdown),
                repeats=1,
            )
        return async_task(
            _execute,
            *call_args,
            task_name=resolved_name,
        )

    return register_task(
        TaskHandle(
            name=resolved_name,
            func=func,
            enqueue=enqueue,
            bind=bind,
            max_retries=max_retries,
        )
    )


__all__ = ["django_q_task"]
