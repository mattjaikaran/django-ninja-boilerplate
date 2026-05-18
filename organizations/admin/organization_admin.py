from django.contrib import admin

from organizations.models import Organization, OrganizationMembership


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "slug", "owner__email"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["owner"]


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ["organization", "user", "role", "is_active", "created_at"]
    list_filter = ["role", "is_active", "created_at"]
    search_fields = ["organization__name", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["organization", "user", "invited_by"]
