"""Backend-neutral task queue facade."""

from api.tasks.contract import (
    TaskContext,
    TaskDispatchDisabled,
    TaskHandle,
    TaskMaxRetriesExceeded,
    TaskRetry,
)
from api.tasks.loader import get_task_decorator

shared_task = get_task_decorator()

__all__ = [
    "TaskContext",
    "TaskDispatchDisabled",
    "TaskHandle",
    "TaskMaxRetriesExceeded",
    "TaskRetry",
    "shared_task",
]
