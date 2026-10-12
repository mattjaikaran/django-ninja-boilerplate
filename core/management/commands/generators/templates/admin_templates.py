"""Admin templates for code generation."""

# Rendered with str.format: {first_party_imports} imports the app's models.
RBAC_ADMIN_TEMPLATE = '''"""RBAC admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

{first_party_imports}


class RolePermissionInline(TabularInline):
    model = RolePermission
    extra = 0


@admin.register(Permission)
class PermissionAdmin(ModelAdmin):
    list_display = ["name", "codename", "content_type", "created_at"]
    list_filter = ["content_type", "created_at"]
    search_fields = ["name", "codename", "description"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display = ["name", "is_default", "permission_count", "created_at"]
    list_filter = ["is_default", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [RolePermissionInline]

    @admin.display(description="Permissions")
    def permission_count(self, obj):
        return obj.permissions.count()


@admin.register(UserRole)
class UserRoleAdmin(ModelAdmin):
    list_display = [
        "user",
        "role",
        "content_type",
        "object_id",
        "is_global",
        "created_at",
    ]
    list_filter = ["role", "content_type", "created_at"]
    search_fields = ["user__email", "role__name"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(boolean=True, description="Global")
    def is_global(self, obj):
        return obj.is_global


@admin.register(RolePermission)
class RolePermissionAdmin(ModelAdmin):
    list_display = ["role", "permission", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["role__name", "permission__name"]
    readonly_fields = ["created_at", "updated_at"]
'''
