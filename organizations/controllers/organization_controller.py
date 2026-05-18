import logging

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

from api.decorators import handle_exceptions, log_api_call
from organizations.schemas import (
    CreateOrganizationSchema,
    InviteMemberSchema,
    OrganizationMembershipSchema,
    OrganizationSchema,
    UpdateMemberRoleSchema,
    UpdateOrganizationSchema,
)
from organizations.services import OrganizationService

logger = logging.getLogger(__name__)


@api_controller("/organizations", tags=["Organizations"], auth=JWTAuth())
class OrganizationController:
    def __init__(self):
        self.service = OrganizationService()

    @http_get("/", response={200: list[OrganizationSchema]})
    @handle_exceptions()
    @log_api_call()
    def list_organizations(self, request):
        return 200, self.service.list_organizations(request.user)

    @http_post("/", response={201: OrganizationSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_organization(self, request, payload: CreateOrganizationSchema):
        return 201, self.service.create_organization(request.user, payload)

    @http_get("/{org_id}", response={200: OrganizationSchema, 403: dict, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_organization(self, request, org_id: str):
        return 200, self.service.get_organization(org_id, request.user)

    @http_put("/{org_id}", response={200: OrganizationSchema, 403: dict, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_organization(
        self, request, org_id: str, payload: UpdateOrganizationSchema
    ):
        return 200, self.service.update_organization(org_id, request.user, payload)

    @http_delete("/{org_id}", response={204: None, 403: dict, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_organization(self, request, org_id: str):
        self.service.delete_organization(org_id, request.user)
        return 204, None

    @http_get(
        "/{org_id}/members",
        response={200: list[OrganizationMembershipSchema], 403: dict, 404: dict},
    )
    @handle_exceptions()
    @log_api_call()
    def list_members(self, request, org_id: str):
        return 200, self.service.list_members(org_id, request.user)

    @http_post(
        "/{org_id}/members",
        response={201: OrganizationMembershipSchema, 403: dict, 404: dict, 409: dict},
    )
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def invite_member(self, request, org_id: str, payload: InviteMemberSchema):
        return 201, self.service.invite_member(org_id, request.user, payload)

    @http_put(
        "/{org_id}/members/{member_id}",
        response={200: OrganizationMembershipSchema, 403: dict, 404: dict},
    )
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_member_role(
        self, request, org_id: str, member_id: str, payload: UpdateMemberRoleSchema
    ):
        return 200, self.service.update_member_role(
            org_id, member_id, request.user, payload
        )

    @http_delete(
        "/{org_id}/members/{member_id}",
        response={204: None, 403: dict, 404: dict},
    )
    @handle_exceptions()
    @log_api_call()
    def remove_member(self, request, org_id: str, member_id: str):
        self.service.remove_member(org_id, member_id, request.user)
        return 204, None

    @http_post(
        "/{org_id}/leave",
        response={204: None, 400: dict, 403: dict, 404: dict},
    )
    @handle_exceptions()
    @log_api_call()
    def leave_organization(self, request, org_id: str):
        self.service.leave_organization(org_id, request.user)
        return 204, None
