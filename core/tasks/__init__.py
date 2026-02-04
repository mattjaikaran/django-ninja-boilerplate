"""Task management package for Celery task improvements.

This package provides:
- Enhanced base task class with progress tracking
- Task progress tracking and storage
- Periodic task management utilities
- Dead letter queue handling for failed tasks
- API endpoints for task status and management
"""

from core.tasks.base import ProgressTask
from core.tasks.dlq import DeadLetterQueue
from core.tasks.progress import TaskProgressTracker
from core.tasks.scheduler import PeriodicTaskManager

__all__ = [
    "DeadLetterQueue",
    "PeriodicTaskManager",
    "ProgressTask",
    "TaskProgressTracker",
]
