"""Django admin registration for the decisions app."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from decisions.models import DecisionFixture


@admin.register(DecisionFixture)
class DecisionFixtureAdmin(ModelAdmin):
    """Admin for stored decision fixtures."""

    list_display = ["kind", "name", "description", "created_at"]
    list_filter = ["kind", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
