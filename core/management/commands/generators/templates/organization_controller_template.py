"""Organization controller template."""

ORGANIZATION_CONTROLLER_TEMPLATE = '''"""Organization controllers."""

import logging
from uuid import UUID
from typing import List

from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import (
    create_endpoint,
    delete_endpoint,
    detail_endpoint,
    list_endpoint,
    update_endpoint,
)
from {app_name}.models import Organization, OrganizationMember
from {app_name}.schemas.organization_schema import (
    OrganizationSchema,
    OrganizationListSchema,
    CreateOrganizationSchema,
    UpdateOrganizationSchema,
    OrganizationMemberSchema,
    InviteMemberSchema,
    UpdateMemberRoleSchema,
    OrganizationStatsSchema,
    TransferOwnershipSchema,
    UpdateOrganizationSettingsSchema,
)
from {app_name}.services.organization_service import OrganizationService

User = get_user_model()
logger = logging.getLogger(__name__)


@api_controller("/organizations", tags=["Organizations"])
class OrganizationController:
    """Organization management controller."""

    @list_endpoint(cache_timeout=300)
    @http_get("/", response={{200: List[OrganizationListSchema]}})
    def list_user_organizations(self, request):
        """List organizations user belongs to."""
        user = request.user
        organizations = OrganizationService.get_user_organizations(user)

        result = []
        for org in organizations:
            member = org.members.get(user=user, status="active")
            result.append({{
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "description": org.description,
                "size": org.size,
                "active_member_count": org.active_member_count,
                "user_role": member.role,
                "last_active_at": member.last_active_at,
            }})

        return 200, result

    @create_endpoint()
    @http_post("/", response={{201: OrganizationSchema}})
    def create_organization(self, request, payload: CreateOrganizationSchema):
        """Create a new organization."""
        user = request.user

        try:
            organization = OrganizationService.create_organization(
                name=payload.name,
                owner=user,
                description=payload.description,
                website=payload.website,
                email=payload.email,
                phone=payload.phone,
                address=payload.address,
                industry=payload.industry,
                size=payload.size,
            )
            return 201, organization
        except Exception as e:
            logger.error(f"Error creating organization: {{e}}")
            return 400, {{"error": str(e)}}

    @detail_endpoint(cache_timeout=300)
    @http_get("/{{str:org_id}}", response={{200: OrganizationSchema, 404: dict}})
    def get_organization(self, request, org_id: str):
        """Get organization details."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)

        # Check if user can access this organization
        if not OrganizationService.can_user_access_organization(user, organization):
            return 403, {{"error": "Access denied"}}

        return 200, organization

    @update_endpoint()
    @http_put("/{{str:org_id}}", response={{200: OrganizationSchema, 404: dict}})
    def update_organization(self, request, org_id: str, payload: UpdateOrganizationSchema):
        """Update organization details."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)

        # Check if user is admin
        member = get_object_or_404(
            OrganizationMember,
            organization=organization,
            user=user,
            status="active"
        )

        if not member.can_manage_members:
            return 403, {{"error": "Permission denied"}}

        # Apply updates
        for key, value in payload.dict(exclude_unset=True).items():
            if hasattr(organization, key):
                setattr(organization, key, value)
        organization.save()

        return 200, organization

    @delete_endpoint()
    @http_delete("/{{str:org_id}}", response={{204: dict, 404: dict}})
    def delete_organization(self, request, org_id: str):
        """Delete organization (only owner can do this)."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)

        # Check if user is owner
        member = get_object_or_404(
            OrganizationMember,
            organization=organization,
            user=user,
            role="owner",
            status="active"
        )

        organization.is_active = False
        organization.save()

        return 204, {{"message": "Organization deleted successfully"}}

    @detail_endpoint(cache_timeout=300)
    @http_get("/{{str:org_id}}/stats", response={{200: OrganizationStatsSchema}})
    def get_organization_stats(self, request, org_id: str):
        """Get organization statistics."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)

        if not OrganizationService.can_user_access_organization(user, organization):
            return 403, {{"error": "Access denied"}}

        stats = OrganizationService.get_organization_stats(organization)
        return 200, stats

    @list_endpoint(cache_timeout=300)
    @http_get("/{{str:org_id}}/members", response={{200: List[OrganizationMemberSchema]}})
    def list_organization_members(self, request, org_id: str):
        """List organization members."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)

        if not OrganizationService.can_user_access_organization(user, organization):
            return 403, {{"error": "Access denied"}}

        members = organization.members.filter(status="active").select_related("user", "invited_by")
        return 200, members

    @create_endpoint()
    @http_post("/{{str:org_id}}/members/invite", response={{201: OrganizationMemberSchema}})
    def invite_member(self, request, org_id: str, payload: InviteMemberSchema):
        """Invite a new member to the organization."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)

        try:
            member = OrganizationService.invite_member(
                organization=organization,
                email=payload.email,
                role=payload.role,
                invited_by=user
            )
            return 201, member
        except Exception as e:
            logger.error(f"Error inviting member: {{e}}")
            return 400, {{"error": str(e)}}

    @update_endpoint()
    @http_put("/{{str:org_id}}/members/{{str:user_id}}/role", response={{200: OrganizationMemberSchema}})
    def update_member_role(self, request, org_id: str, user_id: str, payload: UpdateMemberRoleSchema):
        """Update a member's role."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)
        target_user = get_object_or_404(User, id=user_id)

        success = OrganizationService.update_member_role(
            organization=organization,
            user_to_update=target_user,
            new_role=payload.role,
            updated_by=user
        )

        if not success:
            return 403, {{"error": "Permission denied or invalid operation"}}

        member = organization.members.get(user=target_user)
        return 200, member

    @delete_endpoint()
    @http_delete("/{{str:org_id}}/members/{{str:user_id}}", response={{204: dict}})
    def remove_member(self, request, org_id: str, user_id: str):
        """Remove a member from the organization."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)
        target_user = get_object_or_404(User, id=user_id)

        success = OrganizationService.remove_member(
            organization=organization,
            user_to_remove=target_user,
            removed_by=user
        )

        if not success:
            return 403, {{"error": "Permission denied"}}

        return 204, {{"message": "Member removed successfully"}}

    @create_endpoint()
    @http_post("/{{str:org_id}}/transfer-ownership", response={{200: dict}})
    def transfer_ownership(self, request, org_id: str, payload: TransferOwnershipSchema):
        """Transfer organization ownership."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)
        new_owner = get_object_or_404(User, id=payload.new_owner_user_id)

        try:
            success = OrganizationService.transfer_ownership(
                organization=organization,
                new_owner=new_owner,
                current_owner=user
            )

            if success:
                return 200, {{"message": "Ownership transferred successfully"}}
            else:
                return 400, {{"error": "Transfer failed"}}
        except Exception as e:
            logger.error(f"Error transferring ownership: {{e}}")
            return 400, {{"error": str(e)}}

    @update_endpoint()
    @http_put("/{{str:org_id}}/settings", response={{200: dict}})
    def update_organization_settings(self, request, org_id: str, payload: UpdateOrganizationSettingsSchema):
        """Update organization settings."""
        user = request.user

        organization = get_object_or_404(Organization, id=org_id)

        # Check if user is admin
        member = get_object_or_404(
            OrganizationMember,
            organization=organization,
            user=user,
            status="active"
        )

        if not member.can_manage_members:
            return 403, {{"error": "Permission denied"}}

        organization.settings.update(payload.settings)
        organization.save(update_fields=["settings"])

        return 200, {{"message": "Settings updated successfully", "settings": organization.settings}}


@api_controller("/invitations", tags=["Organization Invitations"])
class OrganizationInvitationController:
    """Organization invitation management."""

    @list_endpoint(cache_timeout=300)
    @http_get("/", response={{200: List}})
    def list_user_invitations(self, request):
        """List pending invitations for the authenticated user."""
        user = request.user

        invitations = OrganizationMember.objects.filter(
            user=user,
            status="pending"
        ).select_related("organization", "invited_by")

        result = []
        for invitation in invitations:
            result.append({{
                "id": str(invitation.id),
                "organization_name": invitation.organization.name,
                "organization_slug": invitation.organization.slug,
                "invited_by_username": invitation.invited_by.username if invitation.invited_by else None,
                "role": invitation.role,
                "invited_at": invitation.invited_at,
                "expires_at": invitation.invitation_expires_at,
                "status": invitation.status,
            }})

        return 200, result

    @create_endpoint()
    @http_post("/{{str:invitation_id}}/accept", response={{200: dict}})
    def accept_invitation(self, request, invitation_id: str):
        """Accept an organization invitation."""
        user = request.user

        invitation = get_object_or_404(
            OrganizationMember,
            id=invitation_id,
            user=user,
            status="pending"
        )

        success = OrganizationService.accept_invitation(invitation)

        if success:
            return 200, {{"message": "Invitation accepted successfully"}}
        else:
            return 400, {{"error": "Invitation expired or invalid"}}

    @delete_endpoint()
    @http_delete("/{{str:invitation_id}}/decline", response={{204: dict}})
    def decline_invitation(self, request, invitation_id: str):
        """Decline an organization invitation."""
        user = request.user

        invitation = get_object_or_404(
            OrganizationMember,
            id=invitation_id,
            user=user,
            status="pending"
        )

        invitation.delete()
        return 204, {{"message": "Invitation declined"}}
'''
