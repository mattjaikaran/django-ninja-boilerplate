from django.contrib import admin
from unfold.admin import ModelAdmin

from billing.models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(ModelAdmin):
    list_display = [
        "name",
        "amount",
        "currency",
        "interval",
        "is_active",
        "stripe_price_id",
        "created_at",
    ]
    list_filter = ["is_active", "interval", "currency"]
    search_fields = ["name", "stripe_price_id", "stripe_product_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = [
        "user",
        "plan",
        "status",
        "stripe_subscription_id",
        "current_period_end",
        "cancel_at_period_end",
        "created_at",
    ]
    list_filter = ["status", "cancel_at_period_end", "plan"]
    search_fields = ["user__email", "stripe_subscription_id", "stripe_customer_id"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["user"]
