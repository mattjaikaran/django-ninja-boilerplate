"""API Key model for machine-to-machine authentication."""

import hashlib
import secrets

from django.conf import settings
from django.db import models

from core.models.base import TimestampedModel


class APIKey(TimestampedModel):
    """API Key for programmatic access.

    Keys are formatted as {prefix}.{secret} where prefix is used for lookup
    and secret is hashed for verification. The raw key is only shown once
    at creation time.
    """

    PREFIX_LENGTH = 8
    SECRET_LENGTH = 48

    prefix = models.CharField(max_length=8, unique=True, db_index=True, editable=False)
    hashed_key = models.CharField(max_length=128, editable=False)
    name = models.CharField(
        max_length=255, help_text="Human-readable label for this key"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    scopes = models.JSONField(
        default=list,
        blank=True,
        help_text='Granular permissions, e.g. ["read:todos", "write:todos"]',
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "core_api_key"
        ordering = ["-created_at"]
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}...)"

    @classmethod
    def generate_key(cls) -> tuple[str, str, str]:
        """Generate a new API key.

        Returns:
            Tuple of (prefix, raw_key, hashed_key).
            raw_key is the full key shown to the user once: {prefix}.{secret}
        """
        prefix = secrets.token_hex(cls.PREFIX_LENGTH // 2)
        secret = secrets.token_urlsafe(cls.SECRET_LENGTH)
        raw_key = f"{prefix}.{secret}"
        hashed = cls.hash_key(raw_key)
        return prefix, raw_key, hashed

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Hash a raw API key using SHA-256."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def verify(self, raw_key: str) -> bool:
        """Verify a raw key against the stored hash."""
        return self.hashed_key == self.hash_key(raw_key)

    @property
    def is_valid(self) -> bool:
        """Check if key is not revoked and not expired."""
        if self.revoked:
            return False
        if self.expires_at:
            from django.utils import timezone

            return self.expires_at > timezone.now()
        return True
