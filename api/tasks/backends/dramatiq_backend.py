"""Dramatiq adapter for the backend-neutral task contract."""

from __future__ import annotations

from typing import Any

import dramatiq
from django.conf import settings
from dramatiq.brokers.redis import RedisBroker

from api.tasks.contract import TaskHandle, execute_task, register_task, task_name
from api.utils.redis_url import normalize_redis_url

_broker_url = normalize_redis_url(settings.REDIS_URL)
dramatiq.set_broker(RedisBroker(url=_broker_url))


@dramatiq.actor(max_retries=0)
def _execute(
    name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    attempt: int,
) -> None:
    execute_task(name, args, kwargs, attempt)


def dramatiq_task(
    func,
    *,
    name: str | None = None,
    bind: bool = False,
    max_retries: int = 3,
    **options: Any,
) -> TaskHandle:
    """Wrap a function as a Dramatiq task with the uniform contract."""
    if options:
        unknown = ", ".join(sorted(options))
        raise TypeError(f"Unsupported Dramatiq task options: {unknown}")

    resolved_name = task_name(func, name)

    def enqueue(
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        countdown: float,
        attempt: int,
    ) -> Any:
        return _execute.send_with_options(
            args=(resolved_name, args, kwargs, attempt),
            delay=int(countdown * 1000) if countdown > 0 else None,
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


__all__ = ["dramatiq_task"]
