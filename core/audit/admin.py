"""Admin configuration for Audit Logs.

Provides a read-only admin interface for viewing and searching audit logs.
Designed for compliance and debugging purposes.
"""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from core.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    """Admin interface for viewing audit logs.

    This admin is read-only to maintain audit trail integrity.
    Supports filtering, searching, and exporting audit data.
    """

    list_display = [
        "timestamp",
        "action_badge",
        "user_display",
        "model_name",
        "object_id_short",
        "ip_address",
        "success_badge",
    ]

    list_filter = [
        "action",
        "success",
        "model_name",
        "timestamp",
    ]

    search_fields = [
        "user_email",
        "model_name",
        "object_id",
        "ip_address",
        "request_path",
        "request_id",
        "action_description",
    ]

    readonly_fields = [
        "id",
        "action",
        "action_description",
        "user",
        "user_email",
        "model_name",
        "object_id",
        "object_repr",
        "changes_display",
        "previous_state_display",
        "new_state_display",
        "ip_address",
        "user_agent",
        "request_method",
        "request_path",
        "request_id",
        "timestamp",
        "extra_data_display",
        "success",
        "error_message",
    ]

    fieldsets = [
        (
            "Action Details",
            {
                "fields": [
                    "id",
                    "action",
                    "action_description",
                    "success",
                    "error_message",
                    "timestamp",
                ]
            },
        ),
        (
            "User Information",
            {
                "fields": [
                    "user",
                    "user_email",
                ]
            },
        ),
        (
            "Affected Object",
            {
                "fields": [
                    "model_name",
                    "object_id",
                    "object_repr",
                ]
            },
        ),
        (
            "Changes",
            {
                "fields": [
                    "changes_display",
                    "previous_state_display",
                    "new_state_display",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Request Context",
            {
                "fields": [
                    "ip_address",
                    "user_agent",
                    "request_method",
                    "request_path",
                    "request_id",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Extra Data",
            {
                "fields": ["extra_data_display"],
                "classes": ["collapse"],
            },
        ),
    ]

    ordering = ["-timestamp"]
    date_hierarchy = "timestamp"
    list_per_page = 50

    def has_add_permission(self, request):
        """Prevent manual creation of audit logs."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent modification of audit logs."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs."""
        return False

    @admin.display(description="Action")
    def action_badge(self, obj) -> str:
        """Display action as a colored badge."""
        colors = {
            "CREATE": "#28a745",
            "UPDATE": "#17a2b8",
            "DELETE": "#dc3545",
            "SOFT_DELETE": "#fd7e14",
            "RESTORE": "#20c997",
            "LOGIN": "#6f42c1",
            "LOGOUT": "#6c757d",
            "LOGIN_FAILED": "#dc3545",
            "PASSWORD_CHANGE": "#ffc107",
            "PASSWORD_RESET": "#ffc107",
            "API_REQUEST": "#007bff",
            "PERMISSION_CHANGE": "#e83e8c",
            "EXPORT": "#17a2b8",
            "IMPORT": "#28a745",
            "CUSTOM": "#6c757d",
        }
        color = colors.get(obj.action, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_action_display(),
        )

    @admin.display(description="User")
    def user_display(self, obj) -> str:
        """Display user email or 'Anonymous'."""
        return obj.user_email or "Anonymous"

    @admin.display(description="Object ID")
    def object_id_short(self, obj) -> str:
        """Display shortened object ID."""
        if obj.object_id:
            return (
                obj.object_id[:8] + "..." if len(obj.object_id) > 8 else obj.object_id
            )
        return "-"

    @admin.display(description="Status")
    def success_badge(self, obj) -> str:
        """Display success status as a badge."""
        if obj.success:
            return format_html('<span style="color: #28a745;">Success</span>')
        return format_html('<span style="color: #dc3545;">Failed</span>')

    @admin.display(description="Changes")
    def changes_display(self, obj) -> str:
        """Display changes as formatted JSON."""
        if obj.changes:
            import json

            return format_html(
                '<pre style="white-space: pre-wrap; max-height: 300px; overflow: auto;">{}</pre>',
                json.dumps(obj.changes, indent=2, default=str),
            )
        return "-"

    @admin.display(description="Previous State")
    def previous_state_display(self, obj) -> str:
        """Display previous state as formatted JSON."""
        if obj.previous_state:
            import json

            return format_html(
                '<pre style="white-space: pre-wrap; max-height: 300px; overflow: auto;">{}</pre>',
                json.dumps(obj.previous_state, indent=2, default=str),
            )
        return "-"

    @admin.display(description="New State")
    def new_state_display(self, obj) -> str:
        """Display new state as formatted JSON."""
        if obj.new_state:
            import json

            return format_html(
                '<pre style="white-space: pre-wrap; max-height: 300px; overflow: auto;">{}</pre>',
                json.dumps(obj.new_state, indent=2, default=str),
            )
        return "-"

    @admin.display(description="Extra Data")
    def extra_data_display(self, obj) -> str:
        """Display extra data as formatted JSON."""
        if obj.extra_data:
            import json

            return format_html(
                '<pre style="white-space: pre-wrap; max-height: 300px; overflow: auto;">{}</pre>',
                json.dumps(obj.extra_data, indent=2, default=str),
            )
        return "-"
