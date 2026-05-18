from django.contrib import admin
from unfold.admin import ModelAdmin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ["title", "type", "user", "is_read", "created_at"]
    list_filter = ["type", "is_read"]
    search_fields = ["title", "body", "user__email"]
