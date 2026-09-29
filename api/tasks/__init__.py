"""Backend-neutral task queue facade."""

from api.tasks.contract import (
    TaskContext,
    TaskHandle,
    TaskMaxRetriesExceeded,
    TaskRetry,
)
from api.tasks.loader import get_task_decorator

shared_task = get_task_decorator()

__all__ = [
    "TaskContext",
    "TaskHandle",
    "TaskMaxRetriesExceeded",
    "TaskRetry",
    "shared_task",
]
