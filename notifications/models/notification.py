from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models.base import TimestampedModel


class Notification(TimestampedModel):
    NOTIFICATION_TYPES = [
        ("in_app", "In App"),
        ("email", "Email"),
        ("push", "Push"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default="in_app",
        db_index=True,
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    action_url = models.CharField(max_length=500, blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
        ]

    def mark_read(self) -> None:
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at", "updated_at"])

    def __str__(self) -> str:
        return f"{self.type}: {self.title} -> {self.user_id}"
