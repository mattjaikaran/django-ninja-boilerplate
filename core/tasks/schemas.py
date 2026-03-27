"""Pydantic schemas for task management API.

This module provides request/response schemas for:
- Task status and progress endpoints
- Periodic task management
- Dead letter queue operations
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from core.schemas.base_schema import CamelCaseSchema

# =============================================================================
# Task Status Schemas
# =============================================================================


class TaskStatusEnum(str, Enum):
    """Task execution status choices."""

    PENDING = "pending"
    STARTED = "started"
    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


class TaskProgressSchema(CamelCaseSchema):
    """Schema for task progress information."""

    task_id: str
    progress: int = Field(..., ge=0, le=100)
    message: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class TaskStatusSchema(CamelCaseSchema):
    """Schema for full task status."""

    task_id: str
    celery_state: str | None = None
    database_status: str | None = None
    progress: int = 0
    message: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None


class TaskResultSchema(CamelCaseSchema):
    """Schema for task result response."""

    id: str
    task_id: str
    name: str
    status: TaskStatusEnum
    progress: int
    message: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None


class TaskListSchema(CamelCaseSchema):
    """Schema for listing tasks with pagination."""

    items: list[TaskResultSchema]
    total: int
    page: int
    per_page: int


class TaskStatsSchema(CamelCaseSchema):
    """Schema for task execution statistics."""

    total: int = 0
    pending: int = 0
    running: int = 0
    success: int = 0
    failure: int = 0
    retry: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float | None = None


# =============================================================================
# Periodic Task Schemas
# =============================================================================


class ScheduleTypeEnum(str, Enum):
    """Periodic task schedule type."""

    INTERVAL = "interval"
    CRONTAB = "crontab"
    CLOCKED = "clocked"


class IntervalScheduleSchema(CamelCaseSchema):
    """Schema for interval-based schedule."""

    every: int = Field(..., gt=0)
    period: str = Field(
        ...,
        description="Period type: seconds, minutes, hours, days",
    )


class CrontabScheduleSchema(CamelCaseSchema):
    """Schema for crontab-based schedule."""

    minute: str = "*"
    hour: str = "*"
    day_of_week: str = "*"
    day_of_month: str = "*"
    month_of_year: str = "*"


class PeriodicTaskSchema(CamelCaseSchema):
    """Schema for periodic task response."""

    id: int
    name: str
    task: str
    enabled: bool
    schedule_type: ScheduleTypeEnum
    schedule: IntervalScheduleSchema | CrontabScheduleSchema | dict | None = None
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    one_off: bool = False
    start_time: datetime | None = None
    expires: datetime | None = None
    last_run_at: datetime | None = None
    total_run_count: int = 0
    description: str = ""
    date_changed: datetime | None = None


class CreateIntervalTaskSchema(CamelCaseSchema):
    """Schema for creating an interval-based periodic task."""

    name: str = Field(..., min_length=1, max_length=200)
    task: str = Field(..., min_length=1, max_length=200)
    every: int = Field(..., gt=0)
    period: str = Field(
        default="seconds",
        description="Period type: seconds, minutes, hours, days",
    )
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    one_off: bool = False
    start_time: datetime | None = None
    expires: datetime | None = None
    description: str = ""


class CreateCrontabTaskSchema(CamelCaseSchema):
    """Schema for creating a crontab-based periodic task."""

    name: str = Field(..., min_length=1, max_length=200)
    task: str = Field(..., min_length=1, max_length=200)
    minute: str = "*"
    hour: str = "*"
    day_of_week: str = "*"
    day_of_month: str = "*"
    month_of_year: str = "*"
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    one_off: bool = False
    start_time: datetime | None = None
    expires: datetime | None = None
    description: str = ""


class UpdatePeriodicTaskSchema(CamelCaseSchema):
    """Schema for updating a periodic task."""

    name: str | None = None
    enabled: bool | None = None
    args: list[Any] | None = None
    kwargs: dict[str, Any] | None = None
    one_off: bool | None = None
    start_time: datetime | None = None
    expires: datetime | None = None
    description: str | None = None


class SchedulerStatsSchema(CamelCaseSchema):
    """Schema for scheduler statistics."""

    total_tasks: int = 0
    enabled_tasks: int = 0
    disabled_tasks: int = 0
    one_off_tasks: int = 0
    interval_tasks: int = 0
    crontab_tasks: int = 0
    clocked_tasks: int = 0
    tasks_run_24h: int = 0


# =============================================================================
# Dead Letter Queue Schemas
# =============================================================================


class DLQPriorityEnum(str, Enum):
    """DLQ entry priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DLQEntrySchema(CamelCaseSchema):
    """Schema for DLQ entry response."""

    id: str
    task_id: str
    task_name: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    exception_type: str
    exception_message: str
    traceback: str = ""
    priority: DLQPriorityEnum
    retry_count: int
    max_retries: int
    can_retry: bool
    last_retry_at: datetime | None = None
    is_resolved: bool
    resolution_notes: str = ""
    created_at: datetime
    updated_at: datetime


class DLQListSchema(CamelCaseSchema):
    """Schema for listing DLQ entries with pagination."""

    items: list[DLQEntrySchema]
    total: int


class DLQResolveSchema(CamelCaseSchema):
    """Schema for resolving a DLQ entry."""

    notes: str = ""


class DLQBulkResolveSchema(CamelCaseSchema):
    """Schema for bulk resolving DLQ entries."""

    entry_ids: list[str]
    notes: str = ""


class DLQRetryResponseSchema(CamelCaseSchema):
    """Schema for retry response."""

    success: bool
    new_task_id: str | None = None
    message: str = ""


class DLQBulkRetrySchema(CamelCaseSchema):
    """Schema for bulk retry request."""

    task_name: str | None = None
    priority: DLQPriorityEnum | None = None
    limit: int = Field(default=10, le=100)


class DLQBulkRetryResponseSchema(CamelCaseSchema):
    """Schema for bulk retry response."""

    attempted: int
    succeeded: int
    failed: int
    task_ids: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class DLQStatsSchema(CamelCaseSchema):
    """Schema for DLQ statistics."""

    total: int = 0
    pending: int = 0
    resolved: int = 0
    low_priority: int = 0
    normal_priority: int = 0
    high_priority: int = 0
    critical_priority: int = 0
    can_retry: int = 0
    exhausted_retries: int = 0
    top_failed_tasks: list[dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Common Response Schemas
# =============================================================================


class TaskActionResponseSchema(CamelCaseSchema):
    """Schema for task action response."""

    success: bool
    message: str
    task_id: str | None = None


class CleanupResponseSchema(CamelCaseSchema):
    """Schema for cleanup operation response."""

    success: bool
    deleted: int
    message: str = ""
