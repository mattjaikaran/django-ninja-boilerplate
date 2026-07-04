"""Admin configuration for API keys."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from core.models.api_key import APIKey


@admin.register(APIKey)
class APIKeyAdmin(ModelAdmin):
    """Admin for API keys. Never displays the hashed key value."""

    list_display = [
        "name",
        "prefix",
        "user",
        "revoked",
        "expires_at",
        "last_used_at",
        "created_at",
    ]
    list_filter = ["revoked", "created_at"]
    search_fields = ["name", "prefix", "user__email"]
    readonly_fields = [
        "prefix",
        "hashed_key",
        "last_used_at",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["user"]

    def has_add_permission(self, request):
        return False
