"""Admin templates for code generation."""

RBAC_ADMIN_TEMPLATE = '''"""RBAC admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin
from {app_name}.models import Role, Permission, UserRole, RolePermission


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
    filter_horizontal = ["permissions"]
    readonly_fields = ["created_at", "updated_at"]

    def permission_count(self, obj):
        return obj.permissions.count()
    permission_count.short_description = "Permissions"


@admin.register(UserRole)
class UserRoleAdmin(ModelAdmin):
    list_display = ["user", "role", "content_type", "object_id", "is_global", "created_at"]
    list_filter = ["role", "content_type", "created_at"]
    search_fields = ["user__username", "user__email", "role__name"]
    readonly_fields = ["created_at", "updated_at"]

    def is_global(self, obj):
        return obj.is_global
    is_global.boolean = True
    is_global.short_description = "Global"


@admin.register(RolePermission)
class RolePermissionAdmin(ModelAdmin):
    list_display = ["role", "permission", "created_at"]
    list_filter = ["role", "permission__content_type", "created_at"]
    search_fields = ["role__name", "permission__name"]
    readonly_fields = ["created_at", "updated_at"]
'''

CHAT_ADMIN_TEMPLATE = '''"""Chat admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin
from {app_name}.models import Conversation, ConversationParticipant, Message, MessageReaction


@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = ["title", "type", "created_by", "participant_count", "last_message_at", "is_active"]
    list_filter = ["type", "is_active", "created_at"]
    search_fields = ["title", "description", "created_by__username"]
    readonly_fields = ["created_at", "updated_at", "last_message_at"]
    filter_horizontal = []

    def participant_count(self, obj):
        return obj.participant_count
    participant_count.short_description = "Participants"


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(ModelAdmin):
    list_display = ["user", "conversation", "role", "is_active", "joined_at", "unread_count"]
    list_filter = ["role", "is_active", "joined_at"]
    search_fields = ["user__username", "conversation__title"]
    readonly_fields = ["created_at", "updated_at", "joined_at", "left_at"]

    def unread_count(self, obj):
        return obj.unread_count
    unread_count.short_description = "Unread"


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ["sender", "conversation", "type", "content_preview", "is_active", "created_at"]
    list_filter = ["type", "is_active", "is_edited", "created_at"]
    search_fields = ["content", "sender__username", "conversation__title"]
    readonly_fields = ["created_at", "updated_at", "edited_at"]

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = "Content"


@admin.register(MessageReaction)
class MessageReactionAdmin(ModelAdmin):
    list_display = ["user", "message", "emoji", "created_at"]
    list_filter = ["emoji", "created_at"]
    search_fields = ["user__username", "message__content"]
    readonly_fields = ["created_at", "updated_at"]
'''

ORGANIZATION_ADMIN_TEMPLATE = '''"""Organization admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin
from {app_name}.models import Organization, OrganizationMember


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ["name", "slug", "size", "industry", "is_active", "is_verified", "created_at"]
    list_filter = ["size", "industry", "is_active", "is_verified", "subscription_tier", "created_at"]
    search_fields = ["name", "email", "description"]
    prepopulated_fields = {{"slug": ("name",)}}
    readonly_fields = ["created_at", "updated_at", "active_member_count", "admin_count"]

    fieldsets = (
        ("Basic Information", {{
            "fields": ("name", "slug", "description", "industry", "size")
        }}),
        ("Contact Information", {{
            "fields": ("website", "email", "phone", "address")
        }}),
        ("Business Information", {{
            "fields": ("tax_id", "subscription_tier", "billing_email")
        }}),
        ("Status", {{
            "fields": ("is_active", "is_verified", "settings")
        }}),
        ("Statistics", {{
            "fields": ("active_member_count", "admin_count"),
            "classes": ("collapse",)
        }}),
        ("Timestamps", {{
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }}),
    )


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(ModelAdmin):
    list_display = ["user", "organization", "role", "status", "joined_at", "last_active_at"]
    list_filter = ["role", "status", "joined_at", "last_active_at"]
    search_fields = ["user__username", "user__email", "organization__name"]
    readonly_fields = ["created_at", "updated_at", "joined_at", "last_active_at"]

    fieldsets = (
        ("Member Information", {{
            "fields": ("user", "organization", "role", "status")
        }}),
        ("Invitation Details", {{
            "fields": ("invited_by", "invited_at", "invitation_token", "invitation_expires_at"),
            "classes": ("collapse",)
        }}),
        ("Membership Timeline", {{
            "fields": ("joined_at", "last_active_at"),
            "classes": ("collapse",)
        }}),
        ("Permissions & Preferences", {{
            "fields": ("permissions", "notification_preferences"),
            "classes": ("collapse",)
        }}),
        ("Timestamps", {{
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }}),
    )
'''
