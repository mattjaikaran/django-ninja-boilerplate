"""Backend-neutral task contract and runtime registry."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class TaskFunction(Protocol):
    """Callable task function with standard function metadata."""

    __name__: str
    __qualname__: str
    __module__: str
    __doc__: str | None

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


class TaskRetry(Exception):
    """Signal that the current task must run again after a delay."""

    def __init__(
        self,
        *task_args: Any,
        exc: BaseException | None,
        countdown: float,
        **task_kwargs: Any,
    ) -> None:
        super().__init__(str(exc) if exc else "Task retry requested")
        self.task_args = task_args
        self.task_kwargs = task_kwargs
        self.exc = exc
        self.countdown = countdown


class TaskMaxRetriesExceeded(RuntimeError):
    """Raised when a task exceeds its declared retry limit."""


@dataclass(frozen=True, slots=True)
class TaskContext:
    """Portable context passed to tasks declared with ``bind=True``."""

    name: str
    task_id: str | None = None

    def retry(
        self,
        *args: Any,
        exc: BaseException | None = None,
        countdown: float = 0,
        **kwargs: Any,
    ) -> TaskRetry:
        """Build the retry signal that the task must raise."""
        return TaskRetry(*args, exc=exc, countdown=countdown, **kwargs)


class Enqueue(Protocol):
    """Backend enqueue callback."""

    def __call__(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        countdown: float,
        attempt: int,
    ) -> Any: ...


class TaskHandle:
    """Callable task with uniform dispatch and retry methods."""

    def __init__(
        self,
        *,
        name: str,
        func: TaskFunction,
        enqueue: Enqueue,
        bind: bool,
        max_retries: int,
    ) -> None:
        self.name = name
        self.func = func
        self._enqueue = enqueue
        self.bind = bind
        self.max_retries = max_retries
        self.__name__ = func.__name__
        self.__qualname__ = func.__qualname__
        self.__doc__ = func.__doc__
        self.__module__ = func.__module__

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Run the task synchronously in the current process."""
        return self._invoke(args, kwargs)

    def _invoke(
        self,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        *,
        task_id: str | None = None,
    ) -> Any:
        call_kwargs = dict(kwargs)
        if self.bind:
            context = TaskContext(name=self.name, task_id=task_id)
            return self.func(context, *args, **call_kwargs)
        return self.func(*args, **call_kwargs)

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        """Enqueue the task for immediate asynchronous execution."""
        return self._enqueue(args, kwargs, 0, 0)

    def retry(
        self,
        *args: Any,
        exc: BaseException | None = None,
        countdown: float = 0,
        **kwargs: Any,
    ) -> TaskRetry:
        """Build the retry signal that the task must raise."""
        return TaskRetry(*args, exc=exc, countdown=countdown, **kwargs)

    def redispatch(
        self,
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
        countdown: float,
        attempt: int,
    ) -> Any:
        """Enqueue the current invocation again after a delay."""
        return self._enqueue(args, dict(kwargs), countdown, attempt)


_registry: dict[str, TaskHandle] = {}


def register_task(handle: TaskHandle) -> TaskHandle:
    """Register a task for serialized worker dispatch."""
    _registry[handle.name] = handle
    return handle


def execute_task(
    name: str,
    args: tuple[Any, ...] | list[Any],
    kwargs: Mapping[str, Any] | None = None,
    attempt: int = 0,
) -> Any:
    """Execute a registered task and translate a retry request."""
    handle = _registry[name]
    invocation_args = tuple(args)
    invocation_kwargs = dict(kwargs or {})
    try:
        result = handle._invoke(invocation_args, invocation_kwargs)
        logger.info("Task completed: %s", name)
        return result
    except TaskRetry as retry:
        if attempt >= handle.max_retries:
            raise TaskMaxRetriesExceeded(
                f"Task '{name}' exceeded {handle.max_retries} retries."
            ) from retry.exc or retry
        retry_args = retry.task_args or invocation_args
        retry_kwargs = retry.task_kwargs or invocation_kwargs
        return handle.redispatch(
            retry_args,
            retry_kwargs,
            retry.countdown,
            attempt + 1,
        )


def task_name(func: TaskFunction, explicit_name: str | None) -> str:
    """Return a stable task name."""
    return explicit_name or f"{func.__module__}.{func.__qualname__}"


__all__ = [
    "TaskContext",
    "TaskHandle",
    "TaskMaxRetriesExceeded",
    "TaskRetry",
    "execute_task",
    "register_task",
    "task_name",
]
