from django.contrib import admin
from unfold.admin import ModelAdmin

from webhooks.models import Webhook, WebhookDelivery


@admin.register(Webhook)
class WebhookAdmin(ModelAdmin):
    list_display = ["name", "url", "is_active", "created_by", "created_at", "id"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "url"]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(ModelAdmin):
    list_display = [
        "webhook",
        "event",
        "response_status",
        "attempt_count",
        "delivered_at",
        "created_at",
        "id",
    ]
    list_filter = ["event", "response_status", "created_at"]
    search_fields = ["webhook__name", "event"]
