from django.conf import settings
from django.db import models

from core.models.base import TimestampedModel


class ActiveOrganizationManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class Organization(TimestampedModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True, default="")
    logo_url = models.URLField(blank=True, default="")
    website = models.URLField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="owned_organizations",
    )

    objects = models.Manager()
    active_objects = ActiveOrganizationManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class OrganizationMembership(TimestampedModel):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invitations",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "user")]
        ordering = ["-created_at"]

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def is_admin(self) -> bool:
        return self.role in ["owner", "admin"]
