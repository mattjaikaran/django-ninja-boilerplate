"""One-Time Password models for authentication.

This module provides OTP models for:
- 6-digit numeric codes for mobile/iOS apps
- Magic link tokens for passwordless authentication
- Email verification tokens
- Password reset tokens
"""

import random
import secrets
import string
from datetime import timedelta
from enum import Enum

from django.conf import settings
from django.db import models
from django.utils import timezone


class OTPPurpose(str, Enum):
    """Purpose of the OTP."""

    LOGIN = "LOGIN"
    SIGNUP_VERIFICATION = "SIGNUP_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_CHANGE = "EMAIL_CHANGE"
    PHONE_VERIFICATION = "PHONE_VERIFICATION"
    TWO_FACTOR = "TWO_FACTOR"
    MAGIC_LINK = "MAGIC_LINK"


class OTPDeliveryMethod(str, Enum):
    """Delivery method for the OTP."""

    EMAIL = "EMAIL"
    SMS = "SMS"
    PUSH = "PUSH"


class OneTimePassword(models.Model):
    """Model for storing one-time passwords for user verification.

    Supports both:
    - 6-digit numeric codes for mobile apps (SMS/push)
    - Long tokens for magic links (email)
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="otp_codes",
        help_text="User this OTP belongs to",
    )
    code = models.CharField(
        max_length=6,
        blank=True,
        help_text="6-digit numeric OTP code for mobile apps",
    )
    token = models.CharField(
        max_length=255,
        unique=True,
        help_text="Long token for magic links",
    )
    purpose = models.CharField(
        max_length=50,
        choices=[(p.value, p.value) for p in OTPPurpose],
        default=OTPPurpose.LOGIN.value,
        help_text="Purpose of this OTP",
    )
    delivery_method = models.CharField(
        max_length=20,
        choices=[(m.value, m.value) for m in OTPDeliveryMethod],
        default=OTPDeliveryMethod.EMAIL.value,
        help_text="How the OTP was delivered",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this OTP was created",
    )
    expires_at = models.DateTimeField(
        help_text="When this OTP expires",
    )
    is_used = models.BooleanField(
        default=False,
        help_text="Whether this OTP has been used",
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this OTP was used",
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of verification attempts",
    )
    max_attempts = models.PositiveIntegerField(
        default=5,
        help_text="Maximum allowed verification attempts",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request",
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        help_text="User agent of the request",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata",
    )

    class Meta:
        verbose_name = "One Time Password"
        verbose_name_plural = "One Time Passwords"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose"]),
            models.Index(fields=["token"]),
            models.Index(fields=["code", "user"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["is_used"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"OTP for {self.user.email} ({self.purpose})"

    @classmethod
    def generate_code(cls) -> str:
        """Generate a 6-digit numeric OTP code.

        Returns:
            str: A 6-digit numeric string
        """
        return "".join(random.choices(string.digits, k=6))

    @classmethod
    def generate_token(cls) -> str:
        """Generate a secure random token for magic links.

        Returns:
            str: A secure URL-safe token
        """
        return secrets.token_urlsafe(32)

    @classmethod
    def create_for_user(
        cls,
        user,
        purpose: OTPPurpose = OTPPurpose.LOGIN,
        delivery_method: OTPDeliveryMethod = OTPDeliveryMethod.EMAIL,
        expires_in_minutes: int = 10,
        ip_address: str | None = None,
        user_agent: str = "",
        use_code: bool = True,
        max_attempts: int = 5,
        metadata: dict | None = None,
    ) -> "OneTimePassword":
        """Create a new OTP for a user.

        Args:
            user: The user to create the OTP for
            purpose: Purpose of the OTP
            delivery_method: How the OTP will be delivered
            expires_in_minutes: Minutes until expiration
            ip_address: IP address of the request
            user_agent: User agent string
            use_code: If True, generates 6-digit code; otherwise uses token only
            max_attempts: Maximum verification attempts allowed
            metadata: Additional metadata to store

        Returns:
            OneTimePassword: The created OTP instance
        """
        # Invalidate any existing unused OTPs for the same purpose
        cls.objects.filter(
            user=user,
            purpose=purpose.value if isinstance(purpose, OTPPurpose) else purpose,
            is_used=False,
        ).update(is_used=True)

        code = cls.generate_code() if use_code else ""
        token = cls.generate_token()
        expires_at = timezone.now() + timedelta(minutes=expires_in_minutes)

        return cls.objects.create(
            user=user,
            code=code,
            token=token,
            purpose=purpose.value if isinstance(purpose, OTPPurpose) else purpose,
            delivery_method=(
                delivery_method.value
                if isinstance(delivery_method, OTPDeliveryMethod)
                else delivery_method
            ),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            max_attempts=max_attempts,
            metadata=metadata or {},
        )

    @property
    def is_expired(self) -> bool:
        """Check if the OTP has expired."""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the OTP is still valid (not used, not expired, attempts left)."""
        return (
            not self.is_used
            and not self.is_expired
            and self.attempts < self.max_attempts
        )

    @property
    def remaining_attempts(self) -> int:
        """Get the number of remaining verification attempts."""
        return max(0, self.max_attempts - self.attempts)

    @property
    def time_until_expiry(self) -> timedelta:
        """Get the time remaining until expiration."""
        return max(timedelta(0), self.expires_at - timezone.now())

    def increment_attempts(self) -> None:
        """Increment the attempt counter."""
        self.attempts += 1
        self.save(update_fields=["attempts"])

    def mark_as_used(self) -> None:
        """Mark the OTP as used."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=["is_used", "used_at"])

    def verify_code(self, code: str) -> bool:
        """Verify the provided code against this OTP.

        Args:
            code: The code to verify

        Returns:
            bool: True if the code matches and OTP is valid
        """
        if not self.is_valid:
            return False

        self.increment_attempts()

        if self.code and self.code == code:
            self.mark_as_used()
            return True

        return False

    def verify_token(self, token: str) -> bool:
        """Verify the provided token against this OTP.

        Args:
            token: The token to verify

        Returns:
            bool: True if the token matches and OTP is valid
        """
        if not self.is_valid:
            return False

        self.increment_attempts()

        if self.token == token:
            self.mark_as_used()
            return True

        return False


class OTPRateLimit(models.Model):
    """Rate limiting for OTP requests.

    Prevents brute force attacks and abuse by limiting
    how often OTPs can be requested.
    """

    identifier = models.CharField(
        max_length=255,
        db_index=True,
        help_text="User ID, email, phone, or IP address",
    )
    purpose = models.CharField(
        max_length=50,
        choices=[(p.value, p.value) for p in OTPPurpose],
        default=OTPPurpose.LOGIN.value,
        help_text="Purpose of the OTP request",
    )
    request_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of requests in the current window",
    )
    window_start = models.DateTimeField(
        auto_now_add=True,
        help_text="Start of the rate limit window",
    )
    blocked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If blocked, when the block expires",
    )

    class Meta:
        verbose_name = "OTP Rate Limit"
        verbose_name_plural = "OTP Rate Limits"
        unique_together = ["identifier", "purpose"]
        indexes = [
            models.Index(fields=["identifier", "purpose"]),
            models.Index(fields=["window_start"]),
            models.Index(fields=["blocked_until"]),
        ]

    def __str__(self):
        return f"Rate limit for {self.identifier} ({self.purpose})"

    @classmethod
    def check_rate_limit(
        cls,
        identifier: str,
        purpose: str,
        max_requests: int = 5,
        window_minutes: int = 15,
        block_minutes: int = 60,
    ) -> tuple[bool, str | None]:
        """Check if the identifier is rate limited.

        Args:
            identifier: User ID, email, phone, or IP address
            purpose: Purpose of the OTP request
            max_requests: Maximum requests allowed in the window
            window_minutes: Size of the rate limit window in minutes
            block_minutes: How long to block after exceeding limit

        Returns:
            tuple: (is_allowed, error_message)
        """
        now = timezone.now()
        window_start = now - timedelta(minutes=window_minutes)

        rate_limit, created = cls.objects.get_or_create(
            identifier=identifier,
            purpose=purpose,
            defaults={"window_start": now, "request_count": 0},
        )

        # Check if blocked
        if rate_limit.blocked_until and rate_limit.blocked_until > now:
            remaining = rate_limit.blocked_until - now
            minutes = int(remaining.total_seconds() / 60) + 1
            return False, f"Too many requests. Try again in {minutes} minutes."

        # Reset if window has passed
        if rate_limit.window_start < window_start:
            rate_limit.window_start = now
            rate_limit.request_count = 0
            rate_limit.blocked_until = None

        # Check if exceeding limit
        if rate_limit.request_count >= max_requests:
            rate_limit.blocked_until = now + timedelta(minutes=block_minutes)
            rate_limit.save()
            return False, f"Rate limit exceeded. Try again in {block_minutes} minutes."

        # Increment counter
        rate_limit.request_count += 1
        rate_limit.save()

        return True, None

    @classmethod
    def cleanup_expired(cls) -> int:
        """Remove expired rate limit records.

        Returns:
            int: Number of records deleted
        """
        cutoff = timezone.now() - timedelta(hours=24)
        deleted, _ = cls.objects.filter(window_start__lt=cutoff).delete()
        return deleted
