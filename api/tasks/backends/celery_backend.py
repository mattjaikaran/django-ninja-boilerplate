"""Celery adapter for the backend-neutral task contract."""

from __future__ import annotations

from typing import Any

from celery import shared_task as celery_shared_task

from api.tasks.contract import TaskHandle, TaskRetry, register_task, task_name


def celery_task(
    func,
    *,
    name: str | None = None,
    bind: bool = False,
    max_retries: int = 3,
    **options: Any,
) -> TaskHandle:
    """Wrap a function as a Celery task with the uniform contract."""
    resolved_name = task_name(func, name)
    handle: TaskHandle

    @celery_shared_task(
        bind=True,
        name=resolved_name,
        max_retries=max_retries,
        **options,
    )
    def runner(celery_self, *args: Any, **kwargs: Any) -> Any:
        try:
            task_id = getattr(celery_self.request, "id", None)
            return handle._invoke(args, kwargs, task_id=task_id)
        except TaskRetry as retry:
            retry_options: dict[str, Any] = {
                "exc": retry.exc,
                "countdown": retry.countdown,
            }
            if retry.task_args:
                retry_options["args"] = retry.task_args
            if retry.task_kwargs:
                retry_options["kwargs"] = retry.task_kwargs
            raise celery_self.retry(**retry_options) from retry.exc

    def enqueue(
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        countdown: float,
        attempt: int,
    ) -> Any:
        del attempt
        return runner.apply_async(
            args=args,
            kwargs=kwargs,
            countdown=countdown or None,
        )

    handle = TaskHandle(
        name=resolved_name,
        func=func,
        enqueue=enqueue,
        bind=bind,
        max_retries=max_retries,
    )
    return register_task(handle)


__all__ = ["celery_task"]
