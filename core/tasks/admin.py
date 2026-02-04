"""Admin interface for task management.

This module provides Django admin interfaces for:
- TaskResult model (task execution history)
- DeadLetterQueueEntry model (failed tasks)
"""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from core.tasks.models import DeadLetterQueueEntry, TaskResult, TaskStatus


@admin.register(TaskResult)
class TaskResultAdmin(ModelAdmin):
    """Admin interface for TaskResult model."""

    list_display = [
        "task_id_short",
        "name",
        "status_badge",
        "progress_bar",
        "duration_display",
        "created_at",
    ]
    list_filter = ["status", "name", "created_at"]
    search_fields = ["task_id", "name", "error"]
    readonly_fields = [
        "id",
        "task_id",
        "name",
        "status",
        "progress",
        "progress_message",
        "args",
        "kwargs",
        "result",
        "error",
        "traceback",
        "meta",
        "created_at",
        "started_at",
        "completed_at",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Task Information",
            {
                "fields": ("task_id", "name", "status", "progress", "progress_message"),
            },
        ),
        (
            "Input",
            {
                "fields": ("args", "kwargs"),
                "classes": ("collapse",),
            },
        ),
        (
            "Output",
            {
                "fields": ("result", "error", "traceback"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("meta",),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "started_at", "completed_at"),
            },
        ),
    )

    def task_id_short(self, obj):
        """Display shortened task ID."""
        return obj.task_id[:8] + "..." if len(obj.task_id) > 8 else obj.task_id

    task_id_short.short_description = "Task ID"

    def status_badge(self, obj):
        """Display status as a colored badge."""
        colors = {
            TaskStatus.PENDING: "#6c757d",
            TaskStatus.STARTED: "#17a2b8",
            TaskStatus.PROGRESS: "#007bff",
            TaskStatus.SUCCESS: "#28a745",
            TaskStatus.FAILURE: "#dc3545",
            TaskStatus.RETRY: "#ffc107",
            TaskStatus.REVOKED: "#6c757d",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def progress_bar(self, obj):
        """Display progress as a progress bar."""
        color = "#28a745" if obj.progress == 100 else "#007bff"
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; '
            'border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; height: 20px; background-color: {};">'
            '<span style="color: white; font-size: 11px; padding-left: 5px;">'
            "{}%</span></div></div>",
            obj.progress,
            color,
            obj.progress,
        )

    progress_bar.short_description = "Progress"

    def duration_display(self, obj):
        """Display task duration."""
        if obj.duration:
            if obj.duration < 1:
                return f"{obj.duration * 1000:.0f}ms"
            if obj.duration < 60:
                return f"{obj.duration:.1f}s"
            minutes = int(obj.duration // 60)
            seconds = int(obj.duration % 60)
            return f"{minutes}m {seconds}s"
        return "-"

    duration_display.short_description = "Duration"

    def has_add_permission(self, request):
        """Disable add permission - tasks are created by Celery."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable change permission - tasks are managed by Celery."""
        return False


@admin.register(DeadLetterQueueEntry)
class DeadLetterQueueEntryAdmin(ModelAdmin):
    """Admin interface for DeadLetterQueueEntry model."""

    list_display = [
        "task_id_short",
        "task_name",
        "priority_badge",
        "exception_type",
        "retry_status",
        "is_resolved",
        "created_at",
    ]
    list_filter = [
        "is_resolved",
        "priority",
        "task_name",
        "exception_type",
        "created_at",
    ]
    search_fields = ["task_id", "task_name", "exception_message"]
    readonly_fields = [
        "id",
        "task_id",
        "task_name",
        "args",
        "kwargs",
        "exception_type",
        "exception_message",
        "traceback",
        "retry_count",
        "last_retry_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Task Information",
            {
                "fields": ("task_id", "task_name", "priority"),
            },
        ),
        (
            "Input",
            {
                "fields": ("args", "kwargs"),
                "classes": ("collapse",),
            },
        ),
        (
            "Error Details",
            {
                "fields": ("exception_type", "exception_message", "traceback"),
            },
        ),
        (
            "Retry Information",
            {
                "fields": ("retry_count", "max_retries", "last_retry_at"),
            },
        ),
        (
            "Resolution",
            {
                "fields": ("is_resolved", "resolution_notes"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    actions = ["mark_resolved", "retry_tasks"]

    def task_id_short(self, obj):
        """Display shortened task ID."""
        return obj.task_id[:8] + "..." if len(obj.task_id) > 8 else obj.task_id

    task_id_short.short_description = "Task ID"

    def priority_badge(self, obj):
        """Display priority as a colored badge."""
        colors = {
            DeadLetterQueueEntry.Priority.LOW: "#6c757d",
            DeadLetterQueueEntry.Priority.NORMAL: "#17a2b8",
            DeadLetterQueueEntry.Priority.HIGH: "#ffc107",
            DeadLetterQueueEntry.Priority.CRITICAL: "#dc3545",
        }
        color = colors.get(obj.priority, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_priority_display(),
        )

    priority_badge.short_description = "Priority"

    def retry_status(self, obj):
        """Display retry status."""
        if obj.can_retry:
            return format_html(
                '<span style="color: #28a745;">Can retry ({}/{})</span>',
                obj.retry_count,
                obj.max_retries,
            )
        return format_html(
            '<span style="color: #dc3545;">Exhausted ({}/{})</span>',
            obj.retry_count,
            obj.max_retries,
        )

    retry_status.short_description = "Retry Status"

    @admin.action(description="Mark selected entries as resolved")
    def mark_resolved(self, request, queryset):
        """Admin action to mark entries as resolved."""
        updated = queryset.filter(is_resolved=False).update(
            is_resolved=True,
            resolution_notes="Resolved via admin action",
        )
        self.message_user(request, f"Marked {updated} entries as resolved.")

    @admin.action(description="Retry selected tasks")
    def retry_tasks(self, request, queryset):
        """Admin action to retry selected tasks."""
        from core.tasks.dlq import DeadLetterQueue

        success_count = 0
        fail_count = 0

        for entry in queryset.filter(is_resolved=False):
            if entry.can_retry:
                result = DeadLetterQueue.retry_entry(str(entry.id))
                if result:
                    success_count += 1
                else:
                    fail_count += 1
            else:
                fail_count += 1

        self.message_user(
            request,
            f"Retried {success_count} tasks. {fail_count} tasks could not be retried.",
        )

    def has_add_permission(self, request):
        """Disable add permission - DLQ entries are created by failed tasks."""
        return False
