from typing import Any, Literal

from pydantic import Field

from core.schemas.base_schema import CamelCaseSchema

# Values match organizations.models.OrganizationMembership.ROLE_CHOICES.
MemberRole = Literal["owner", "admin", "member"]
# Django's validate_slug, which Organization.slug (SlugField) uses.
SLUG_PATTERN = r"^[-a-zA-Z0-9_]+$"


class OrganizationSchema(CamelCaseSchema):
    id: str
    name: str
    slug: str
    description: str
    logo_url: str
    website: str
    metadata: dict[str, Any]  # schema-ok: free-form organization metadata
    is_active: bool
    owner_id: str | None
    member_count: int = 0

    @staticmethod
    def resolve_id(obj) -> str:
        return str(obj.id)

    @staticmethod
    def resolve_owner_id(obj) -> str | None:
        return str(obj.owner_id) if obj.owner_id else None

    @staticmethod
    def resolve_member_count(obj) -> int:
        if hasattr(obj, "member_count"):
            return obj.member_count
        return obj.memberships.filter(is_active=True).count()


class CreateOrganizationSchema(CamelCaseSchema):
    name: str = Field(..., min_length=1, max_length=150)
    slug: str | None = Field(None, max_length=150, pattern=SLUG_PATTERN)
    description: str | None = None
    website: str | None = Field(None, max_length=200)


class UpdateOrganizationSchema(CamelCaseSchema):
    name: str | None = Field(None, min_length=1, max_length=150)
    slug: str | None = Field(None, max_length=150, pattern=SLUG_PATTERN)
    description: str | None = None
    logo_url: str | None = Field(None, max_length=200)
    website: str | None = Field(None, max_length=200)
    metadata: dict[str, Any] | None = None  # schema-ok: free-form organization metadata


class OrganizationMembershipSchema(CamelCaseSchema):
    id: str
    organization_id: str
    user_id: str
    role: MemberRole
    is_active: bool
    joined_at: str

    @staticmethod
    def resolve_id(obj) -> str:
        return str(obj.id)

    @staticmethod
    def resolve_organization_id(obj) -> str:
        return str(obj.organization_id)

    @staticmethod
    def resolve_user_id(obj) -> str:
        return str(obj.user_id)

    @staticmethod
    def resolve_joined_at(obj) -> str:
        return obj.created_at.isoformat()


class InviteMemberSchema(CamelCaseSchema):
    user_id: str
    role: MemberRole = "member"


class UpdateMemberRoleSchema(CamelCaseSchema):
    role: MemberRole
