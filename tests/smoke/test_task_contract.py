"""Contract tests for the backend-neutral task facade."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from api.tasks.contract import (
    TaskContext,
    TaskHandle,
    TaskMaxRetriesExceeded,
    TaskRetry,
    execute_task,
    register_task,
)
from api.tasks.loader import get_task_decorator


class EnqueueRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any], float, int]] = []

    def __call__(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        countdown: float,
        attempt: int,
    ) -> int:
        self.calls.append((args, kwargs, countdown, attempt))
        return len(self.calls)


def test_task_handle_runs_synchronously_and_delays() -> None:
    recorder = EnqueueRecorder()

    def add(left: int, right: int) -> int:
        return left + right

    task = TaskHandle(
        name="tests.add",
        func=add,
        enqueue=recorder,
        bind=False,
        max_retries=3,
    )

    assert task(2, 3) == 5
    assert task.delay(4, right=5) == 1
    assert recorder.calls == [((4,), {"right": 5}, 0, 0)]


def test_bound_task_receives_portable_context() -> None:
    recorder = EnqueueRecorder()

    def identify(context: TaskContext, value: str) -> tuple[str, str | None, str]:
        return context.name, context.task_id, value

    task = TaskHandle(
        name="tests.identify",
        func=identify,
        enqueue=recorder,
        bind=True,
        max_retries=3,
    )

    assert task("value") == ("tests.identify", None, "value")


def test_retry_uses_explicit_payload_and_increments_attempt() -> None:
    recorder = EnqueueRecorder()
    task: TaskHandle

    def retrying(value: str) -> None:
        raise task.retry("replacement", countdown=12, marker=value)

    task = register_task(
        TaskHandle(
            name="tests.retrying",
            func=retrying,
            enqueue=recorder,
            bind=False,
            max_retries=2,
        )
    )

    assert execute_task(task.name, ("original",), {}, attempt=0) == 1
    assert recorder.calls == [(("replacement",), {"marker": "original"}, 12, 1)]


def test_retry_reuses_current_payload_when_not_overridden() -> None:
    recorder = EnqueueRecorder()
    task: TaskHandle

    def retrying(value: str, *, marker: str) -> None:
        raise task.retry(countdown=3)

    task = register_task(
        TaskHandle(
            name="tests.retrying-current-payload",
            func=retrying,
            enqueue=recorder,
            bind=False,
            max_retries=2,
        )
    )

    execute_task(task.name, ("original",), {"marker": "kept"}, attempt=0)
    assert recorder.calls == [(("original",), {"marker": "kept"}, 3, 1)]


def test_retry_limit_fails_loud() -> None:
    recorder = EnqueueRecorder()
    task: TaskHandle

    def retrying() -> None:
        raise task.retry(countdown=1)

    task = register_task(
        TaskHandle(
            name="tests.retry-limit",
            func=retrying,
            enqueue=recorder,
            bind=False,
            max_retries=1,
        )
    )

    with pytest.raises(TaskMaxRetriesExceeded, match="exceeded 1 retries"):
        execute_task(task.name, (), {}, attempt=1)
    assert recorder.calls == []


def test_retry_signal_keeps_exception_and_payload() -> None:
    error = ValueError("broken")
    task_retry = TaskRetry("value", exc=error, countdown=7, flag=True)

    assert task_retry.task_args == ("value",)
    assert task_retry.task_kwargs == {"flag": True}
    assert task_retry.exc is error
    assert task_retry.countdown == 7


@override_settings(TASK_BACKEND="not-real")
def test_unknown_backend_fails_loud() -> None:
    with pytest.raises(ImproperlyConfigured, match="Unknown TASK_BACKEND"):
        get_task_decorator()


@override_settings(TASK_BACKEND="missing")
def test_missing_backend_package_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    from api.tasks import loader

    monkeypatch.setitem(
        loader._BACKENDS,
        "missing",
        ("package_that_does_not_exist", "task", "missing-package"),
    )
    with pytest.raises(ImproperlyConfigured, match="requires the 'missing-package'"):
        get_task_decorator()


@pytest.mark.parametrize(
    "backend",
    ["celery", "huey", "django_q", "django_rq", "dramatiq"],
)
def test_each_backend_exposes_uniform_contract(backend: str) -> None:
    script = f"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
os.environ['TASK_BACKEND'] = '{backend}'
os.environ['REDIS_URL'] = 'redis://127.0.0.1:6380/0'
import django
django.setup()
from api.tasks.contract import execute_task
if '{backend}' == 'celery':
    from celery.app.task import Task
    def apply_immediately(self, args=None, kwargs=None, **options):
        return self.run(*(args or ()), **(kwargs or {{}}))
    Task.apply_async = apply_immediately
elif '{backend}' == 'huey':
    from api.tasks.backends import huey_backend as adapter
    class ImmediateHueyTask:
        def __call__(self, *args):
            return execute_task(*args)
        def schedule(self, *, args, delay):
            return execute_task(*args)
    adapter._execute = ImmediateHueyTask()
elif '{backend}' == 'django_q':
    from api.tasks.backends import django_q_backend as adapter
    adapter.async_task = lambda worker, *args, **options: worker(*args)
elif '{backend}' == 'django_rq':
    from api.tasks.backends import django_rq_backend as adapter
    class ImmediateQueue:
        def enqueue(self, worker, *args, **options):
            return worker(*args)
        def enqueue_in(self, delay, worker, *args, **options):
            return worker(*args)
    adapter.django_rq.get_queue = lambda name: ImmediateQueue()
elif '{backend}' == 'dramatiq':
    from api.tasks.backends import dramatiq_backend as adapter
    worker = adapter._execute.fn
    class ImmediateActor:
        def send_with_options(self, *, args, delay):
            return worker(*args)
    adapter._execute = ImmediateActor()
from api.tasks import TaskHandle, TaskRetry, shared_task
executions = []
@shared_task(name='tests.backend.{backend}', max_retries=2)
def add(left, right):
    executions.append((left, right))
    return left + right
task_retry = add.retry(1, 2, countdown=5, marker='kept')
assert isinstance(add, TaskHandle)
assert add(2, 3) == 5
add.delay(4, right=5)
assert executions[-1] == (4, 5)
assert add.name == 'tests.backend.{backend}'
assert isinstance(task_retry, TaskRetry)
assert task_retry.task_args == (1, 2)
assert task_retry.task_kwargs == {{'marker': 'kept'}}
assert task_retry.countdown == 5
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
