from core.schemas.base_schema import CamelCaseSchema


class OrganizationSchema(CamelCaseSchema):
    id: str
    name: str
    slug: str
    description: str
    logo_url: str
    website: str
    metadata: dict
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

    class Config:
        from_attributes = True


class CreateOrganizationSchema(CamelCaseSchema):
    name: str
    slug: str | None = None
    description: str | None = None
    website: str | None = None


class UpdateOrganizationSchema(CamelCaseSchema):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    logo_url: str | None = None
    website: str | None = None
    metadata: dict | None = None


class OrganizationMembershipSchema(CamelCaseSchema):
    id: str
    organization_id: str
    user_id: str
    role: str
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

    class Config:
        from_attributes = True


class InviteMemberSchema(CamelCaseSchema):
    user_id: str
    role: str = "member"


class UpdateMemberRoleSchema(CamelCaseSchema):
    role: str
