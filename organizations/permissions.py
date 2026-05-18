from ninja_extra.permissions import BasePermission

from organizations.models import OrganizationMembership


class OrganizationMemberPermission(BasePermission):
    def has_permission(self, request, controller) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        org_id = getattr(request, "organization_id", None)
        if not org_id:
            return False
        return OrganizationMembership.objects.filter(
            organization_id=org_id,
            user=request.user,
            is_active=True,
        ).exists()
