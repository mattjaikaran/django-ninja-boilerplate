from django.conf import settings
from django.db import models

from core.models.base import TimestampedModel


class Webhook(TimestampedModel):
    name = models.CharField(max_length=100)
    url = models.URLField()
    secret = models.CharField(max_length=256, blank=True)
    events = models.JSONField(default=list)
    headers = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="webhooks",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.url})"


class WebhookDelivery(TimestampedModel):
    webhook = models.ForeignKey(
        Webhook, on_delete=models.CASCADE, related_name="deliveries"
    )
    event = models.CharField(max_length=100)
    payload = models.JSONField()
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default="")
    attempt_count = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_successful(self) -> bool:
        return self.response_status is not None and 200 <= self.response_status < 300
