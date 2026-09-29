"""django-rq adapter for the backend-neutral task contract."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import django_rq

from api.tasks.contract import TaskHandle, execute_task, register_task, task_name


def _execute(
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    attempt: int,
) -> Any:
    return execute_task(name, args, kwargs, attempt)


def rq_task(
    func,
    *,
    name: str | None = None,
    bind: bool = False,
    max_retries: int = 3,
    **options: Any,
) -> TaskHandle:
    """Wrap a function as a django-rq task with the uniform contract."""
    if options:
        unknown = ", ".join(sorted(options))
        raise TypeError(f"Unsupported django-rq task options: {unknown}")

    resolved_name = task_name(func, name)

    def enqueue(
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        countdown: float,
        attempt: int,
    ) -> Any:
        queue = django_rq.get_queue("default")
        call_args = (resolved_name, args, kwargs, attempt)
        if countdown > 0:
            return queue.enqueue_in(
                timedelta(seconds=countdown),
                _execute,
                *call_args,
                description=resolved_name,
            )
        return queue.enqueue(
            _execute,
            *call_args,
            description=resolved_name,
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


__all__ = ["rq_task"]
