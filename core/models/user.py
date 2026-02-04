"""User model and custom user manager.

This module defines the custom User model with extended profile fields
and the CustomUserManager for user creation operations.
"""

import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models


class CustomUserManager(BaseUserManager):
    """Custom manager for User model with email-based authentication."""

    use_in_migrations = True

    def create_user(self, email=None, password=None, **extra_fields):
        """Create and return a regular user.

        Args:
            email: User's email address (required)
            password: User's password
            **extra_fields: Additional fields to set on the user

        Returns:
            User: Created user instance

        Raises:
            ValueError: If email is not provided
            ValidationError: If user creation fails validation
        """
        if not email:
            raise ValueError("The Email field must be set")
        normalized_email = self.normalize_email(email).lower()

        # Generate username from email if not provided
        if "username" not in extra_fields or not extra_fields.get("username"):
            extra_fields["username"] = normalized_email.split("@")[0]

        user = self.model(email=normalized_email, **extra_fields)
        user.set_password(password)
        try:
            user.full_clean()
            user.save(using=self._db)
        except ValidationError as e:
            raise ValidationError(e.message_dict) from e
        return user

    def create_superuser(self, email, password, **extra_fields):
        """Create and return a superuser.

        Args:
            email: User's email address
            password: User's password
            **extra_fields: Additional fields to set on the user

        Returns:
            User: Created superuser instance

        Raises:
            ValueError: If is_staff or is_superuser is not True
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)

    def active(self):
        """Return only active users."""
        return self.get_queryset().filter(is_active=True)

    def staff(self):
        """Return only staff users."""
        return self.get_queryset().filter(is_staff=True)

    def superusers(self):
        """Return only superusers."""
        return self.get_queryset().filter(is_superuser=True)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model with extended profile fields.

    Uses email for authentication and includes profile fields like
    avatar, bio, phone, and timezone preferences.
    """

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Authentication fields
    email = models.EmailField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="User's email address (used for login)",
    )
    username = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="User's unique username",
    )
    password = models.CharField(max_length=128)

    # Profile fields
    first_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="User's first name",
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="User's last name",
    )
    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True,
        help_text="User's profile avatar",
    )
    bio = models.TextField(
        blank=True,
        default="",
        max_length=500,
        help_text="Short bio or description",
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="User's phone number",
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="User's location",
    )
    website = models.URLField(
        blank=True,
        default="",
        help_text="User's website URL",
    )
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="User's preferred timezone",
    )

    # Status fields
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether the user account is active",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Whether the user can access admin site",
    )
    is_superuser = models.BooleanField(
        default=False,
        help_text="Whether the user has all permissions",
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's email is verified",
    )

    # Timestamps
    date_joined = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the user account was created",
    )
    last_login = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the user last logged in",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the user profile was last updated",
    )

    # Preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text="Whether to receive email notifications",
    )
    push_notifications = models.BooleanField(
        default=True,
        help_text="Whether to receive push notifications",
    )

    # Metadata (flexible JSON field for additional data)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata for the user",
    )

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["-date_joined"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_verified"]),
        ]
        verbose_name = "user"
        verbose_name_plural = "users"

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    @property
    def initials(self) -> str:
        """Get user's initials."""
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        if self.username:
            return self.username[:2].upper()
        return "??"

    @property
    def display_name(self) -> str:
        """Get display name (full name or username)."""
        return self.full_name if self.first_name else self.username

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        """Validate the user instance."""
        super().clean()
        # Normalize email
        self.email = self.email.lower()

        # Check for duplicate email
        if User.objects.filter(email=self.email).exclude(pk=self.pk).exists():
            raise ValidationError({"email": "A user with that email already exists."})

        # Check for duplicate username
        if User.objects.filter(username=self.username).exclude(pk=self.pk).exists():
            raise ValidationError(
                {"username": "A user with that username already exists."}
            )

    def get_short_name(self) -> str:
        """Return the short name for the user."""
        return self.first_name or self.username

    def get_full_name(self) -> str:
        """Return the full name for the user."""
        return self.full_name

    def set_metadata(self, key: str, value) -> None:
        """Set a metadata key-value pair."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
        self.save(update_fields=["metadata", "updated_at"])

    def get_metadata(self, key: str, default=None):
        """Get a metadata value by key."""
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)
