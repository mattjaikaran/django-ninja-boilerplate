import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from ninja.errors import HttpError

from organizations.models import Organization, OrganizationMembership
from organizations.schemas import (
    CreateOrganizationSchema,
    InviteMemberSchema,
    UpdateMemberRoleSchema,
    UpdateOrganizationSchema,
)

logger = logging.getLogger(__name__)

User = get_user_model()


class OrganizationService:
    def list_organizations(self, user: Any):
        membership_org_ids = OrganizationMembership.objects.filter(
            user=user,
            is_active=True,
        ).values_list("organization_id", flat=True)
        return Organization.objects.filter(
            id__in=membership_org_ids,
            is_active=True,
        )

    def get_organization(self, org_id: str, user: Any) -> Organization:
        org = get_object_or_404(Organization, id=org_id, is_active=True)
        is_member = OrganizationMembership.objects.filter(
            organization=org,
            user=user,
            is_active=True,
        ).exists()
        if not is_member:
            raise HttpError(403, "You are not a member of this organization")
        return org

    def create_organization(
        self, user: Any, data: CreateOrganizationSchema
    ) -> Organization:
        slug = data.slug or slugify(data.name)
        if Organization.objects.filter(slug=slug).exists():
            base_slug = slug
            counter = 1
            while Organization.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
        org = Organization.objects.create(
            name=data.name,
            slug=slug,
            description=data.description or "",
            website=data.website or "",
            owner=user,
        )
        OrganizationMembership.objects.create(
            organization=org,
            user=user,
            role="owner",
        )
        return org

    def update_organization(
        self, org_id: str, user: Any, data: UpdateOrganizationSchema
    ) -> Organization:
        org = self.get_organization(org_id, user)
        membership = get_object_or_404(
            OrganizationMembership,
            organization=org,
            user=user,
            is_active=True,
        )
        if not membership.is_admin:
            raise HttpError(403, "Only admins and owners can update this organization")
        update_fields = []
        if data.name is not None:
            org.name = data.name
            update_fields.append("name")
        if data.slug is not None:
            org.slug = data.slug
            update_fields.append("slug")
        if data.description is not None:
            org.description = data.description
            update_fields.append("description")
        if data.logo_url is not None:
            org.logo_url = data.logo_url
            update_fields.append("logo_url")
        if data.website is not None:
            org.website = data.website
            update_fields.append("website")
        if data.metadata is not None:
            org.metadata = data.metadata
            update_fields.append("metadata")
        if update_fields:
            update_fields.append("updated_at")
            org.save(update_fields=update_fields)
        return org

    def delete_organization(self, org_id: str, user: Any) -> None:
        org = self.get_organization(org_id, user)
        membership = get_object_or_404(
            OrganizationMembership,
            organization=org,
            user=user,
            is_active=True,
        )
        if not membership.is_owner:
            raise HttpError(403, "Only the owner can delete this organization")
        org.is_active = False
        org.save(update_fields=["is_active", "updated_at"])

    def list_members(self, org_id: str, user: Any):
        org = self.get_organization(org_id, user)
        return OrganizationMembership.objects.filter(
            organization=org,
            is_active=True,
        ).select_related("user", "invited_by")

    def invite_member(
        self, org_id: str, user: Any, data: InviteMemberSchema
    ) -> OrganizationMembership:
        org = self.get_organization(org_id, user)
        acting_membership = get_object_or_404(
            OrganizationMembership,
            organization=org,
            user=user,
            is_active=True,
        )
        if not acting_membership.is_admin:
            raise HttpError(403, "Only admins and owners can invite members")
        invite_user = get_object_or_404(User, id=data.user_id)
        existing = OrganizationMembership.objects.filter(
            organization=org,
            user=invite_user,
        ).first()
        if existing:
            if existing.is_active:
                raise HttpError(409, "User is already a member of this organization")
            existing.is_active = True
            existing.role = data.role
            existing.invited_by = user
            existing.save(
                update_fields=["is_active", "role", "invited_by", "updated_at"]
            )
            return existing
        return OrganizationMembership.objects.create(
            organization=org,
            user=invite_user,
            role=data.role,
            invited_by=user,
        )

    def update_member_role(
        self,
        org_id: str,
        member_id: str,
        user: Any,
        data: UpdateMemberRoleSchema,
    ) -> OrganizationMembership:
        org = self.get_organization(org_id, user)
        acting_membership = get_object_or_404(
            OrganizationMembership,
            organization=org,
            user=user,
            is_active=True,
        )
        if not acting_membership.is_owner:
            raise HttpError(403, "Only owners can change member roles")
        target_membership = get_object_or_404(
            OrganizationMembership,
            id=member_id,
            organization=org,
            is_active=True,
        )
        target_membership.role = data.role
        target_membership.save(update_fields=["role", "updated_at"])
        return target_membership

    def remove_member(self, org_id: str, member_id: str, user: Any) -> None:
        org = self.get_organization(org_id, user)
        acting_membership = get_object_or_404(
            OrganizationMembership,
            organization=org,
            user=user,
            is_active=True,
        )
        if not acting_membership.is_admin:
            raise HttpError(403, "Only admins and owners can remove members")
        target_membership = get_object_or_404(
            OrganizationMembership,
            id=member_id,
            organization=org,
            is_active=True,
        )
        if target_membership.user == user and acting_membership.is_owner:
            raise HttpError(
                400, "Owner cannot remove themselves; transfer ownership first"
            )
        target_membership.is_active = False
        target_membership.save(update_fields=["is_active", "updated_at"])

    def leave_organization(self, org_id: str, user: Any) -> None:
        org = self.get_organization(org_id, user)
        membership = get_object_or_404(
            OrganizationMembership,
            organization=org,
            user=user,
            is_active=True,
        )
        if membership.is_owner:
            other_owners = OrganizationMembership.objects.filter(
                organization=org,
                role="owner",
                is_active=True,
            ).exclude(user=user)
            if not other_owners.exists():
                raise HttpError(
                    400,
                    "You are the last owner. Transfer ownership before leaving.",
                )
        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])
