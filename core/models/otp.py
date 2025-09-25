from django.conf import settings
from django.db import models


class OneTimePassword(models.Model):
    """Model for storing one-time passwords for user verification."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "One Time Password"
        verbose_name_plural = "One Time Passwords"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["token"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["is_used"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"OTP for {self.user.email}"
