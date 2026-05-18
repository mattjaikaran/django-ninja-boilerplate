from django.conf import settings
from django.db import models

from core.models.base import TimestampedModel


class FileUpload(TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="file_uploads",
    )
    key = models.CharField(max_length=500)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.BigIntegerField(null=True, blank=True)
    is_confirmed = models.BooleanField(default=False, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    is_public = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.filename

    @property
    def s3_url(self) -> str | None:
        if not self.is_confirmed:
            return None
        bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
        if not bucket:
            return None
        return f"https://{bucket}.s3.amazonaws.com/{self.key}"
