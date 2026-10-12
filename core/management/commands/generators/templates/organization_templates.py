"""Templates for the organization feature generator.

Each template is verbatim code. ``fill_imports`` puts the first-party imports,
which depend on the app name, where ``{first_party_imports}`` stands.
"""

from core.management.commands.generators.codegen import (
    fill_imports,
    from_import,
    package_init,
)

ORGANIZATION_MODELS_TEMPLATE = '''"""Organization models: organizations and their members."""

from django.conf import settings
from django.db import models

{first_party_imports}


class Organization(AbstractBaseModel):
    """A company or team. ``is_active`` is False after deletion."""

    SIZE_CHOICES = [
        ("startup", "Startup (1-10)"),
        ("small", "Small (11-50)"),
        ("medium", "Medium (51-200)"),
        ("large", "Large (201-1000)"),
        ("enterprise", "Enterprise (1000+)"),
    ]
    TIER_CHOICES = [
        ("free", "Free"),
        ("basic", "Basic"),
        ("pro", "Professional"),
        ("enterprise", "Enterprise"),
    ]

    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.JSONField(default=dict, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    size = models.CharField(max_length=20, choices=SIZE_CHOICES, default="startup")
    is_verified = models.BooleanField(default=False)
    settings = models.JSONField(default=dict, blank=True)
    billing_email = models.EmailField(blank=True)
    subscription_tier = models.CharField(
        max_length=20, choices=TIER_CHOICES, default="free"
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name", "is_active"]),
            models.Index(fields=["industry", "size"]),
        ]

    def __str__(self) -> str:
        return self.name


class OrganizationMember(AbstractBaseModel):
    """A user's membership in an organization."""

    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Administrator"),
        ("manager", "Manager"),
        ("member", "Member"),
        ("viewer", "Viewer"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Pending invitation"),
        ("suspended", "Suspended"),
        ("inactive", "Inactive"),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_invitations_sent",
    )
    invited_at = models.DateTimeField(null=True, blank=True)
    invitation_expires_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    last_active_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("organization", "user")]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.organization_id} ({self.role})"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def can_invite(self) -> bool:
        return self.role in ("owner", "admin", "manager")

    @property
    def can_manage_members(self) -> bool:
        return self.role in ("owner", "admin")
'''

ORGANIZATION_SCHEMAS_TEMPLATE = '''"""Organization schemas. Choice values match the organization models."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BeforeValidator, EmailStr, Field

{first_party_imports}

# Serialize UUID primary and foreign keys as strings.
UUIDStr = Annotated[str, BeforeValidator(str)]
MemberRole = Literal["owner", "admin", "manager", "member", "viewer"]
InvitableRole = Literal["admin", "manager", "member", "viewer"]
MemberStatus = Literal["active", "pending", "suspended", "inactive"]
OrganizationSize = Literal["startup", "small", "medium", "large", "enterprise"]


class OrganizationSchema(CamelCaseSchema):
    id: UUIDStr
    name: str
    slug: str
    description: str
    website: str
    email: str
    phone: str
    address: dict[str, str]
    industry: str
    size: OrganizationSize
    is_verified: bool
    subscription_tier: str
    active_member_count: int
    user_role: MemberRole
    created_at: datetime
    updated_at: datetime


class CreateOrganizationSchema(CamelCaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    website: str = Field("", max_length=200)
    email: EmailStr | Literal[""] = ""
    phone: str = Field("", max_length=20)
    address: dict[str, str] = Field(default_factory=dict)
    industry: str = Field("", max_length=100)
    size: OrganizationSize = "startup"


class UpdateOrganizationSchema(CamelCaseSchema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    website: str | None = Field(None, max_length=200)
    email: EmailStr | Literal[""] | None = None
    phone: str | None = Field(None, max_length=20)
    address: dict[str, str] | None = None
    industry: str | None = Field(None, max_length=100)
    size: OrganizationSize | None = None


class OrganizationStatsSchema(CamelCaseSchema):
    total_members: int
    pending_invitations: int
    admin_count: int
    member_count: int


class OrganizationMemberSchema(CamelCaseSchema):
    id: UUIDStr
    organization_id: UUIDStr
    user_id: UUIDStr
    username: str
    email: str
    role: MemberRole
    status: MemberStatus
    invited_by_id: UUIDStr | None = None
    invited_at: datetime | None = None
    invitation_expires_at: datetime | None = None
    joined_at: datetime | None = None

    @staticmethod
    def resolve_username(obj) -> str:
        return obj.user.username

    @staticmethod
    def resolve_email(obj) -> str:
        return obj.user.email


class InvitationSchema(CamelCaseSchema):
    id: UUIDStr
    organization_id: UUIDStr
    organization_name: str
    role: MemberRole
    invited_by_id: UUIDStr | None = None
    invited_at: datetime | None = None
    invitation_expires_at: datetime | None = None

    @staticmethod
    def resolve_organization_name(obj) -> str:
        return obj.organization.name


class InviteMemberSchema(CamelCaseSchema):
    email: EmailStr
    role: InvitableRole = "member"


class UpdateMemberRoleSchema(CamelCaseSchema):
    role: InvitableRole


class TransferOwnershipSchema(CamelCaseSchema):
    new_owner_user_id: UUID


class OrganizationSettingsSchema(CamelCaseSchema):
    settings: dict[str, Any]  # schema-ok: free-form organization settings
'''

ORGANIZATION_SERVICE_TEMPLATE = '''"""Organization business logic. Every query is scoped to the user's memberships."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, OuterRef, Q, QuerySet, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify

{first_party_imports}

User = get_user_model()


class OrganizationService:
    """Organizations the user is an active member of. Others are a 404."""

    def _memberships(self, user: Any) -> QuerySet[OrganizationMember]:
        """Return the user's active memberships in active organizations."""
        return OrganizationMember.objects.filter(
            user=user, status="active", organization__is_active=True
        )

    def _organizations(self, user: Any) -> QuerySet[Organization]:
        """Return the user's organizations with member count and the user's role."""
        role = self._memberships(user).filter(organization=OuterRef("pk"))
        return Organization.objects.filter(
            is_active=True,
            id__in=self._memberships(user).values("organization_id"),
        ).annotate(
            active_member_count=Count("members", filter=Q(members__status="active")),
            user_role=Subquery(role.values("role")[:1]),
        )

    def _membership(self, org_id: UUID, user: Any) -> OrganizationMember:
        """Return the user's active membership in the organization or raise 404."""
        return get_object_or_404(
            self._memberships(user).select_related("organization"),
            organization_id=org_id,
        )

    def _unique_slug(self, name: str) -> str:
        """Return a slug for the name that no organization uses yet."""
        base = slugify(name) or "organization"
        slug, counter = base, 1
        while Organization.objects.filter(slug=slug).exists():
            counter += 1
            slug = f"{base}-{counter}"
        return slug

    def list_for_user(self, user: Any) -> QuerySet[Organization]:
        """Return the organizations the user belongs to."""
        return self._organizations(user)

    def get_for_user(self, org_id: UUID, user: Any) -> Organization:
        """Return one of the user's organizations."""
        return get_object_or_404(self._organizations(user), id=org_id)

    def create(self, user: Any, payload: CreateOrganizationSchema) -> Organization:
        """Create an organization with the user as its owner."""
        with transaction.atomic():
            organization = Organization.objects.create(
                name=payload.name,
                slug=self._unique_slug(payload.name),
                description=payload.description,
                website=payload.website,
                email=payload.email,
                phone=payload.phone,
                address=payload.address,
                industry=payload.industry,
                size=payload.size,
                created_by=user,
            )
            OrganizationMember.objects.create(
                organization=organization,
                user=user,
                role="owner",
                status="active",
                joined_at=timezone.now(),
            )
        return self.get_for_user(organization.id, user)

    def update(
        self, org_id: UUID, user: Any, payload: UpdateOrganizationSchema
    ) -> Organization:
        """Apply the set fields of the payload. Owners and admins only."""
        membership = self._membership(org_id, user)
        if not membership.can_manage_members:
            raise APIPermissionError("Only owners and admins can edit the organization")
        organization = membership.organization
        for field in payload.model_fields_set:
            value = getattr(payload, field)
            if value is not None:
                setattr(organization, field, value)
        organization.save()
        return self.get_for_user(org_id, user)

    def delete(self, org_id: UUID, user: Any) -> None:
        """Deactivate the organization. Owners only."""
        membership = self._membership(org_id, user)
        if not membership.is_owner:
            raise APIPermissionError("Only the owner can delete the organization")
        organization = membership.organization
        organization.is_active = False
        organization.save(update_fields=["is_active", "updated_at"])

    def stats(self, org_id: UUID, user: Any) -> dict[str, int]:
        """Return member counts for one of the user's organizations."""
        self._membership(org_id, user)
        return OrganizationMember.objects.filter(organization_id=org_id).aggregate(
            total_members=Count("id", filter=Q(status="active")),
            pending_invitations=Count("id", filter=Q(status="pending")),
            admin_count=Count(
                "id", filter=Q(status="active", role__in=("owner", "admin"))
            ),
            member_count=Count("id", filter=Q(status="active", role="member")),
        )

    def list_members(self, org_id: UUID, user: Any) -> QuerySet[OrganizationMember]:
        """Return the active members of one of the user's organizations."""
        self._membership(org_id, user)
        return (
            OrganizationMember.objects.filter(organization_id=org_id, status="active")
            .select_related("user")
            .order_by("joined_at")
        )

    def invite(
        self, org_id: UUID, user: Any, payload: InviteMemberSchema
    ) -> OrganizationMember:
        """Invite an existing user by email. Owners, admins and managers only."""
        membership = self._membership(org_id, user)
        if not membership.can_invite:
            raise APIPermissionError("You cannot invite members to this organization")
        invitee = get_object_or_404(User, email__iexact=payload.email, is_active=True)
        current = OrganizationMember.objects.filter(
            organization_id=org_id, status__in=("active", "pending")
        )
        if current.filter(user=invitee).exists():
            raise ConflictError("The user is already a member or invited")
        if current.count() >= settings.ORGANIZATION_MAX_MEMBERS:
            raise ValidationError("The organization has reached its member limit")
        now = timezone.now()
        invitation, _ = OrganizationMember.objects.update_or_create(
            organization_id=org_id,
            user=invitee,
            defaults={
                "role": payload.role,
                "status": "pending",
                "invited_by": user,
                "invited_at": now,
                "invitation_expires_at": now
                + timedelta(days=settings.ORGANIZATION_INVITATION_EXPIRY_DAYS),
                "joined_at": None,
            },
        )
        return invitation

    def update_member_role(
        self,
        org_id: UUID,
        member_user_id: UUID,
        user: Any,
        payload: UpdateMemberRoleSchema,
    ) -> OrganizationMember:
        """Change an active member's role. Owners only."""
        membership = self._membership(org_id, user)
        if not membership.is_owner:
            raise APIPermissionError("Only the owner can change member roles")
        target = get_object_or_404(
            OrganizationMember.objects.select_related("user"),
            organization_id=org_id,
            user_id=member_user_id,
            status="active",
        )
        if target.is_owner:
            raise ValidationError("Transfer ownership to change the owner's role")
        target.role = payload.role
        target.save(update_fields=["role", "updated_at"])
        return target

    def remove_member(self, org_id: UUID, member_user_id: UUID, user: Any) -> None:
        """Remove a member. Members can leave; owners and admins remove others."""
        membership = self._membership(org_id, user)
        target = get_object_or_404(
            OrganizationMember,
            organization_id=org_id,
            user_id=member_user_id,
            status__in=("active", "pending"),
        )
        if target.is_owner:
            raise ValidationError("Transfer ownership before the owner leaves")
        is_self = target.pk == membership.pk
        if not (
            is_self
            or membership.is_owner
            or (membership.can_manage_members and not target.can_manage_members)
        ):
            raise APIPermissionError("You cannot remove this member")
        target.status = "inactive"
        target.save(update_fields=["status", "updated_at"])

    def transfer_ownership(
        self, org_id: UUID, user: Any, payload: TransferOwnershipSchema
    ) -> OrganizationMember:
        """Make another active member the owner. The old owner becomes admin."""
        membership = self._membership(org_id, user)
        if not membership.is_owner:
            raise APIPermissionError("Only the owner can transfer ownership")
        new_owner = get_object_or_404(
            OrganizationMember.objects.select_related("user"),
            organization_id=org_id,
            user_id=payload.new_owner_user_id,
            status="active",
        )
        if new_owner.pk == membership.pk:
            raise ValidationError("You already own this organization")
        with transaction.atomic():
            membership.role = "admin"
            membership.save(update_fields=["role", "updated_at"])
            new_owner.role = "owner"
            new_owner.save(update_fields=["role", "updated_at"])
        return new_owner

    def update_settings(
        self, org_id: UUID, user: Any, payload: OrganizationSettingsSchema
    ) -> Organization:
        """Merge the payload into the organization settings. Owners and admins."""
        membership = self._membership(org_id, user)
        if not membership.can_manage_members:
            raise APIPermissionError("Only owners and admins can edit settings")
        organization = membership.organization
        organization.settings.update(payload.settings)
        organization.save(update_fields=["settings", "updated_at"])
        return organization

    def _pending_invitations(self, user: Any) -> QuerySet[OrganizationMember]:
        """Return the user's pending invitations to active organizations."""
        return OrganizationMember.objects.filter(
            user=user, status="pending", organization__is_active=True
        ).select_related("organization")

    def list_invitations(self, user: Any) -> QuerySet[OrganizationMember]:
        """Return the user's unexpired invitations."""
        return self._pending_invitations(user).filter(
            invitation_expires_at__gt=timezone.now()
        )

    def accept_invitation(self, invitation_id: UUID, user: Any) -> OrganizationMember:
        """Accept one of the user's unexpired invitations."""
        invitation = get_object_or_404(
            self.list_invitations(user).select_related("user"), id=invitation_id
        )
        invitation.status = "active"
        invitation.joined_at = timezone.now()
        invitation.save(update_fields=["status", "joined_at", "updated_at"])
        return invitation

    def decline_invitation(self, invitation_id: UUID, user: Any) -> None:
        """Decline one of the user's pending invitations."""
        invitation = get_object_or_404(
            self._pending_invitations(user), id=invitation_id
        )
        invitation.status = "inactive"
        invitation.save(update_fields=["status", "updated_at"])
'''

ORGANIZATION_CONTROLLER_TEMPLATE = '''"""Organization controller. The service scopes every route to request.user."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/organizations", tags=["Organizations"], auth=JWTAuth())
class OrganizationController:
    """Organizations the authenticated user is a member of.

    Put static paths before the first /{org_id} handler.
    """

    def __init__(self):
        self.service = OrganizationService()

    @http_get("/", response={200: list[OrganizationSchema]})
    @log_api_call()
    def list_organizations(self, request):
        """List the user's organizations."""
        return 200, self.service.list_for_user(request.user)

    @http_post("/", response={201: OrganizationSchema})
    @log_api_call(include_payload=True)
    def create_organization(self, request, payload: CreateOrganizationSchema):
        """Create an organization owned by the user."""
        return 201, self.service.create(request.user, payload)

    @http_get("/{org_id}", response={200: OrganizationSchema, 404: dict})
    @log_api_call()
    def get_organization(self, request, org_id: UUID):
        """Get one of the user's organizations."""
        return 200, self.service.get_for_user(org_id, request.user)

    @http_put("/{org_id}", response={200: OrganizationSchema, 403: dict, 404: dict})
    @log_api_call(include_payload=True)
    def update_organization(
        self, request, org_id: UUID, payload: UpdateOrganizationSchema
    ):
        """Update an organization. Owners and admins only."""
        return 200, self.service.update(org_id, request.user, payload)

    @http_delete("/{org_id}", response={204: None, 403: dict, 404: dict})
    @log_api_call()
    def delete_organization(self, request, org_id: UUID):
        """Delete an organization. Owner only."""
        self.service.delete(org_id, request.user)
        return 204, None

    @http_get("/{org_id}/stats", response={200: OrganizationStatsSchema, 404: dict})
    @log_api_call()
    def get_organization_stats(self, request, org_id: UUID):
        """Get member counts for an organization."""
        return 200, self.service.stats(org_id, request.user)

    @http_get(
        "/{org_id}/members",
        response={200: list[OrganizationMemberSchema], 404: dict},
    )
    @log_api_call()
    def list_members(self, request, org_id: UUID):
        """List the active members of an organization."""
        return 200, self.service.list_members(org_id, request.user)

    @http_post(
        "/{org_id}/members/invite",
        response={
            201: OrganizationMemberSchema,
            400: dict,
            403: dict,
            404: dict,
            409: dict,
        },
    )
    @log_api_call(include_payload=True)
    def invite_member(self, request, org_id: UUID, payload: InviteMemberSchema):
        """Invite an existing user by email."""
        return 201, self.service.invite(org_id, request.user, payload)

    @http_put(
        "/{org_id}/members/{user_id}/role",
        response={200: OrganizationMemberSchema, 400: dict, 403: dict, 404: dict},
    )
    @log_api_call(include_payload=True)
    def update_member_role(
        self, request, org_id: UUID, user_id: UUID, payload: UpdateMemberRoleSchema
    ):
        """Change a member's role. Owner only."""
        return 200, self.service.update_member_role(
            org_id, user_id, request.user, payload
        )

    @http_delete(
        "/{org_id}/members/{user_id}",
        response={204: None, 400: dict, 403: dict, 404: dict},
    )
    @log_api_call()
    def remove_member(self, request, org_id: UUID, user_id: UUID):
        """Leave the organization, or remove another member."""
        self.service.remove_member(org_id, user_id, request.user)
        return 204, None

    @http_post(
        "/{org_id}/transfer-ownership",
        response={200: OrganizationMemberSchema, 400: dict, 403: dict, 404: dict},
    )
    @log_api_call(include_payload=True)
    def transfer_ownership(
        self, request, org_id: UUID, payload: TransferOwnershipSchema
    ):
        """Make another member the owner. Owner only."""
        return 200, self.service.transfer_ownership(org_id, request.user, payload)

    @http_put(
        "/{org_id}/settings",
        response={200: OrganizationSettingsSchema, 403: dict, 404: dict},
    )
    @log_api_call(include_payload=True)
    def update_organization_settings(
        self, request, org_id: UUID, payload: OrganizationSettingsSchema
    ):
        """Merge settings into the organization. Owners and admins only."""
        return 200, self.service.update_settings(org_id, request.user, payload)
'''

INVITATION_CONTROLLER_TEMPLATE = '''"""Invitation controller. The service scopes every route to request.user."""

from uuid import UUID

from ninja_extra import api_controller, http_get, http_post
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/invitations", tags=["Organization Invitations"], auth=JWTAuth())
class OrganizationInvitationController:
    """Pending organization invitations for the authenticated user.

    Put static paths before the first /{invitation_id} handler.
    """

    def __init__(self):
        self.service = OrganizationService()

    @http_get("/", response={200: list[InvitationSchema]})
    @log_api_call()
    def list_invitations(self, request):
        """List the user's unexpired invitations."""
        return 200, self.service.list_invitations(request.user)

    @http_post(
        "/{invitation_id}/accept",
        response={200: OrganizationMemberSchema, 404: dict},
    )
    @log_api_call()
    def accept_invitation(self, request, invitation_id: UUID):
        """Accept an invitation and join the organization."""
        return 200, self.service.accept_invitation(invitation_id, request.user)

    @http_post("/{invitation_id}/decline", response={204: None, 404: dict})
    @log_api_call()
    def decline_invitation(self, request, invitation_id: UUID):
        """Decline an invitation."""
        self.service.decline_invitation(invitation_id, request.user)
        return 204, None
'''

ORGANIZATION_ADMIN_TEMPLATE = '''"""Organization admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin

{first_party_imports}


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ["name", "slug", "size", "industry", "is_active", "is_verified"]
    list_filter = ["size", "industry", "is_active", "is_verified", "subscription_tier"]
    search_fields = ["name", "email", "description"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (
            "Basic information",
            {"fields": ("name", "slug", "description", "industry", "size")},
        ),
        ("Contact information", {"fields": ("website", "email", "phone", "address")}),
        (
            "Business information",
            {"fields": ("tax_id", "subscription_tier", "billing_email")},
        ),
        ("Status", {"fields": ("is_active", "is_verified", "settings")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(ModelAdmin):
    list_display = ["user", "organization", "role", "status", "joined_at"]
    list_filter = ["role", "status", "joined_at"]
    search_fields = ["user__username", "user__email", "organization__name"]
    readonly_fields = ["created_at", "updated_at", "joined_at", "last_active_at"]
'''

ORGANIZATION_TESTS_TEMPLATE = '''"""Smoke and permission tests for the organization API."""

import pytest

{first_party_imports}


def create_organization(owner, name="Acme"):
    """Create an organization owned by ``owner`` through the service."""
    return OrganizationService().create(owner, CreateOrganizationSchema(name=name))


@pytest.mark.django_db
class TestOrganizationAPI:
    """Smoke and permission tests for organization and invitation endpoints."""

    def test_list_as_member_returns_200(self, authenticated_client):
        client, user = authenticated_client
        organization = create_organization(user)
        response = client.get("/api/organizations/")
        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [str(organization.id)]

    def test_list_requires_authentication(self, api_client):
        response = api_client.get("/api/organizations/")
        assert response.status_code == 401

    def test_non_member_cannot_read_organization(self, authenticated_client):
        client, _ = authenticated_client
        organization = create_organization(UserFactory())
        response = client.get(f"/api/organizations/{organization.id}")
        assert response.status_code == 404

    def test_member_cannot_update_organization(self, authenticated_client):
        client, user = authenticated_client
        owner = UserFactory()
        organization = create_organization(owner)
        service = OrganizationService()
        invitation = service.invite(
            organization.id, owner, InviteMemberSchema(email=user.email)
        )
        service.accept_invitation(invitation.id, user)
        response = client.put(
            f"/api/organizations/{organization.id}",
            {"name": "Renamed"},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_cannot_accept_another_users_invitation(self, authenticated_client):
        client, _ = authenticated_client
        owner = UserFactory()
        organization = create_organization(owner)
        invitation = OrganizationService().invite(
            organization.id, owner, InviteMemberSchema(email=UserFactory().email)
        )
        response = client.post(f"/api/invitations/{invitation.id}/accept")
        assert response.status_code == 404

    def test_create_without_name_returns_422(self, authenticated_client):
        client, _ = authenticated_client
        response = client.post(
            "/api/organizations/", {}, content_type="application/json"
        )
        assert_validation_error(response, field="name")
'''


def render_organization_files(app_name: str) -> dict[str, str]:
    """Return the generated files keyed by path relative to the app directory."""
    return {
        "models/organization.py": fill_imports(
            ORGANIZATION_MODELS_TEMPLATE,
            from_import("core.models", "AbstractBaseModel"),
        ),
        "schemas/organization_schema.py": fill_imports(
            ORGANIZATION_SCHEMAS_TEMPLATE,
            from_import("core.schemas.base_schema", "CamelCaseSchema"),
        ),
        "services/organization_service.py": fill_imports(
            ORGANIZATION_SERVICE_TEMPLATE,
            from_import(
                "api.exceptions",
                "APIPermissionError",
                "ConflictError",
                "ValidationError",
            ),
            from_import(f"{app_name}.models", "Organization", "OrganizationMember"),
            from_import(
                f"{app_name}.schemas",
                "CreateOrganizationSchema",
                "InviteMemberSchema",
                "OrganizationSettingsSchema",
                "TransferOwnershipSchema",
                "UpdateMemberRoleSchema",
                "UpdateOrganizationSchema",
            ),
        ),
        "controllers/organization_controller.py": fill_imports(
            ORGANIZATION_CONTROLLER_TEMPLATE,
            from_import("api.decorators", "log_api_call"),
            from_import(
                f"{app_name}.schemas",
                "CreateOrganizationSchema",
                "InviteMemberSchema",
                "OrganizationMemberSchema",
                "OrganizationSchema",
                "OrganizationSettingsSchema",
                "OrganizationStatsSchema",
                "TransferOwnershipSchema",
                "UpdateMemberRoleSchema",
                "UpdateOrganizationSchema",
            ),
            from_import(f"{app_name}.services", "OrganizationService"),
        ),
        "controllers/invitation_controller.py": fill_imports(
            INVITATION_CONTROLLER_TEMPLATE,
            from_import("api.decorators", "log_api_call"),
            from_import(
                f"{app_name}.schemas",
                "InvitationSchema",
                "OrganizationMemberSchema",
            ),
            from_import(f"{app_name}.services", "OrganizationService"),
        ),
        "admin/organization_admin.py": fill_imports(
            ORGANIZATION_ADMIN_TEMPLATE,
            from_import(f"{app_name}.models", "Organization", "OrganizationMember"),
        ),
        "tests/test_organization.py": fill_imports(
            ORGANIZATION_TESTS_TEMPLATE,
            from_import("core.tests.factories", "UserFactory"),
            from_import(
                f"{app_name}.schemas",
                "CreateOrganizationSchema",
                "InviteMemberSchema",
            ),
            from_import(f"{app_name}.services", "OrganizationService"),
            from_import("tests.utils.assertions", "assert_validation_error"),
        ),
        "models/__init__.py": package_init(
            (f"{app_name}.models.organization", ["Organization", "OrganizationMember"])
        ),
        "schemas/__init__.py": package_init(
            (
                f"{app_name}.schemas.organization_schema",
                [
                    "CreateOrganizationSchema",
                    "InvitationSchema",
                    "InviteMemberSchema",
                    "OrganizationMemberSchema",
                    "OrganizationSchema",
                    "OrganizationSettingsSchema",
                    "OrganizationStatsSchema",
                    "TransferOwnershipSchema",
                    "UpdateMemberRoleSchema",
                    "UpdateOrganizationSchema",
                ],
            )
        ),
        "services/__init__.py": package_init(
            (f"{app_name}.services.organization_service", ["OrganizationService"])
        ),
        "controllers/__init__.py": package_init(
            (
                f"{app_name}.controllers.invitation_controller",
                ["OrganizationInvitationController"],
            ),
            (
                f"{app_name}.controllers.organization_controller",
                ["OrganizationController"],
            ),
        ),
        "admin/__init__.py": package_init(
            (
                f"{app_name}.admin.organization_admin",
                ["OrganizationAdmin", "OrganizationMemberAdmin"],
            )
        ),
    }
