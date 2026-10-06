"""Disabled task backend: ``TASK_BACKEND=none`` runs no worker.

Tasks still register and run synchronously when called directly. Enqueueing
raises ``TaskDispatchDisabled``, because no consumer would ever run the
message.
"""

from __future__ import annotations

from typing import Any

from api.tasks.contract import (
    TaskDispatchDisabled,
    TaskHandle,
    register_task,
    task_name,
)

_BACKENDS = "celery, huey, django_q, django_rq, dramatiq"


def disabled_task(
    func,
    *,
    name: str | None = None,
    bind: bool = False,
    max_retries: int = 3,
    **options: Any,
) -> TaskHandle:
    """Wrap a function whose dispatch fails while no task backend runs."""
    del options  # Queue options have no meaning without a queue.
    resolved_name = task_name(func, name)

    def enqueue(
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        countdown: float,
        attempt: int,
    ) -> Any:
        del args, kwargs, countdown, attempt
        raise TaskDispatchDisabled(
            f"Cannot enqueue task '{resolved_name}': TASK_BACKEND='none' runs no "
            f"worker, so the job would never run. Set TASK_BACKEND to one of "
            f"{_BACKENDS} in .env and start its worker profile "
            f"(docs/TASK_BACKENDS.md), or call the task directly to run it "
            f"in this process."
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


__all__ = ["disabled_task"]
