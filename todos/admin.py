from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Todo


@admin.register(Todo)
class TodoAdmin(ModelAdmin):
    list_display = ["id", "title", "user", "completed", "created_at"]
    search_fields = ["title", "description", "user__username"]
    list_filter = ["completed", "created_at"]
