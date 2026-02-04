"""Feature Flag Admin Configuration.

This module provides Django admin interface for managing feature flags.
"""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import FeatureFlag, FeatureFlagAuditLog


class FeatureFlagAuditLogInline(TabularInline):
    """Inline admin for viewing audit logs."""

    model = FeatureFlagAuditLog
    extra = 0
    readonly_fields = ["action", "changes", "user", "created_at"]
    can_delete = False
    max_num = 0  # Prevent adding new audit logs manually

    def has_add_permission(self, request, obj=None):
        """Prevent adding audit logs manually."""
        return False


@admin.register(FeatureFlag)
class FeatureFlagAdmin(ModelAdmin):
    """Admin configuration for FeatureFlag model."""

    list_display = [
        "name",
        "flag_type",
        "enabled",
        "rollout_percentage",
        "environment_display",
        "time_window_display",
        "updated_at",
    ]
    list_filter = [
        "enabled",
        "flag_type",
        "environments",
        "created_at",
        "updated_at",
    ]
    search_fields = ["name", "description", "tags"]
    readonly_fields = ["id", "created_at", "updated_at", "created_by", "updated_by"]
    ordering = ["name"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "description", "tags"),
            },
        ),
        (
            "Flag Configuration",
            {
                "fields": ("flag_type", "enabled", "rollout_percentage"),
            },
        ),
        (
            "User Targeting",
            {
                "fields": ("user_ids", "excluded_user_ids"),
                "classes": ("collapse",),
            },
        ),
        (
            "A/B Testing",
            {
                "fields": ("variants", "default_variant"),
                "classes": ("collapse",),
            },
        ),
        (
            "Advanced Settings",
            {
                "fields": ("conditions", "environments"),
                "classes": ("collapse",),
            },
        ),
        (
            "Time Window",
            {
                "fields": ("starts_at", "ends_at"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("metadata",),
                "classes": ("collapse",),
            },
        ),
        (
            "Audit Information",
            {
                "fields": (
                    "id",
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [FeatureFlagAuditLogInline]

    def environment_display(self, obj):
        """Display environments in a readable format."""
        if not obj.environments:
            return "All"
        return ", ".join(obj.environments)

    environment_display.short_description = "Environments"

    def time_window_display(self, obj):
        """Display time window in a readable format."""
        if not obj.starts_at and not obj.ends_at:
            return "Always"

        parts = []
        if obj.starts_at:
            parts.append(f"From: {obj.starts_at.strftime('%Y-%m-%d %H:%M')}")
        if obj.ends_at:
            parts.append(f"Until: {obj.ends_at.strftime('%Y-%m-%d %H:%M')}")

        return " | ".join(parts)

    time_window_display.short_description = "Time Window"

    def save_model(self, request, obj, form, change):
        """Save the model and track the user."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

        # Create audit log
        action = "updated" if change else "created"
        FeatureFlagAuditLog.objects.create(
            feature_flag=obj,
            action=action,
            changes={"admin_change": True, "changed_fields": list(form.changed_data)},
            user=request.user,
        )

    actions = ["enable_flags", "disable_flags", "set_rollout_50", "set_rollout_100"]

    @admin.action(description="Enable selected flags")
    def enable_flags(self, request, queryset):
        """Bulk enable selected flags."""
        count = queryset.update(enabled=True)
        for flag in queryset:
            FeatureFlagAuditLog.objects.create(
                feature_flag=flag,
                action="enabled",
                changes={"bulk_action": True},
                user=request.user,
            )
        self.message_user(request, f"Enabled {count} feature flag(s).")

    @admin.action(description="Disable selected flags")
    def disable_flags(self, request, queryset):
        """Bulk disable selected flags."""
        count = queryset.update(enabled=False)
        for flag in queryset:
            FeatureFlagAuditLog.objects.create(
                feature_flag=flag,
                action="disabled",
                changes={"bulk_action": True},
                user=request.user,
            )
        self.message_user(request, f"Disabled {count} feature flag(s).")

    @admin.action(description="Set rollout to 50%")
    def set_rollout_50(self, request, queryset):
        """Set rollout percentage to 50%."""
        count = queryset.update(rollout_percentage=50, flag_type="percentage")
        for flag in queryset:
            FeatureFlagAuditLog.objects.create(
                feature_flag=flag,
                action="rollout_updated",
                changes={"rollout_percentage": 50, "bulk_action": True},
                user=request.user,
            )
        self.message_user(request, f"Set {count} flag(s) to 50% rollout.")

    @admin.action(description="Set rollout to 100%")
    def set_rollout_100(self, request, queryset):
        """Set rollout percentage to 100%."""
        count = queryset.update(rollout_percentage=100, flag_type="percentage")
        for flag in queryset:
            FeatureFlagAuditLog.objects.create(
                feature_flag=flag,
                action="rollout_updated",
                changes={"rollout_percentage": 100, "bulk_action": True},
                user=request.user,
            )
        self.message_user(request, f"Set {count} flag(s) to 100% rollout.")


@admin.register(FeatureFlagAuditLog)
class FeatureFlagAuditLogAdmin(ModelAdmin):
    """Admin configuration for FeatureFlagAuditLog model."""

    list_display = ["feature_flag", "action", "user", "created_at"]
    list_filter = ["action", "created_at", "feature_flag"]
    search_fields = ["feature_flag__name", "action", "user__email"]
    readonly_fields = ["id", "feature_flag", "action", "changes", "user", "created_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        """Prevent manual creation of audit logs."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing audit logs."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs."""
        return False
