from django.conf import settings
from django.db import models

from core.models.base import SoftDeleteModel, TimestampedModel


class Plan(SoftDeleteModel):
    INTERVAL_CHOICES = [
        ("month", "Monthly"),
        ("year", "Yearly"),
        ("week", "Weekly"),
        ("day", "Daily"),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    stripe_price_id = models.CharField(
        max_length=100, unique=True, blank=True, default=""
    )
    stripe_product_id = models.CharField(max_length=100, blank=True, default="")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    interval = models.CharField(
        max_length=10, choices=INTERVAL_CHOICES, default="month"
    )
    features = models.JSONField(default=list)

    class Meta:
        ordering = ["amount"]

    @property
    def is_free(self) -> bool:
        from decimal import Decimal

        return Decimal(str(self.amount)) == Decimal("0.00")

    def __str__(self) -> str:
        return f"{self.name} ({self.interval})"


class Subscription(TimestampedModel):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("canceled", "Canceled"),
        ("past_due", "Past Due"),
        ("trialing", "Trialing"),
        ("incomplete", "Incomplete"),
        ("paused", "Paused"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    stripe_subscription_id = models.CharField(
        max_length=100, unique=True, blank=True, default=""
    )
    stripe_customer_id = models.CharField(
        max_length=100, blank=True, default="", db_index=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="incomplete", db_index=True
    )
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_active(self) -> bool:
        return self.status in ("active", "trialing")

    def __str__(self) -> str:
        return f"{self.user} — {self.plan} ({self.status})"
