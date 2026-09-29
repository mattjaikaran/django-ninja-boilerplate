"""Huey adapter for the backend-neutral task contract."""

from __future__ import annotations

from typing import Any

from huey.contrib.djhuey import task as huey_task

from api.tasks.contract import TaskHandle, execute_task, register_task, task_name


@huey_task(context=True)
def _execute(
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    attempt: int,
    task=None,
) -> Any:
    return execute_task(name, args, kwargs, attempt)


def huey_backend_task(
    func,
    *,
    name: str | None = None,
    bind: bool = False,
    max_retries: int = 3,
    **options: Any,
) -> TaskHandle:
    """Wrap a function as a Huey task with the uniform contract."""
    if options:
        unknown = ", ".join(sorted(options))
        raise TypeError(f"Unsupported Huey task options: {unknown}")

    resolved_name = task_name(func, name)

    def enqueue(
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        countdown: float,
        attempt: int,
    ) -> Any:
        call_args = (resolved_name, args, kwargs, attempt)
        if countdown > 0:
            return _execute.schedule(args=call_args, delay=countdown)
        return _execute(*call_args)

    return register_task(
        TaskHandle(
            name=resolved_name,
            func=func,
            enqueue=enqueue,
            bind=bind,
            max_retries=max_retries,
        )
    )


__all__ = ["huey_backend_task"]
