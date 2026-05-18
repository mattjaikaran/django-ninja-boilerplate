import uuid

from django.utils.deprecation import MiddlewareMixin

from organizations.models import Organization, OrganizationMembership


class OrganizationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        org_id_header = request.headers.get("X-Organization-ID")
        if not org_id_header:
            request.organization = None
            return

        try:
            org_uuid = uuid.UUID(org_id_header)
        except (ValueError, AttributeError):
            request.organization = None
            return

        try:
            org = Organization.objects.get(id=org_uuid, is_active=True)
        except Organization.DoesNotExist:
            request.organization = None
            return

        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            is_member = OrganizationMembership.objects.filter(
                organization=org,
                user=user,
                is_active=True,
            ).exists()
            if is_member:
                request.organization = org
                return

        request.organization = None
