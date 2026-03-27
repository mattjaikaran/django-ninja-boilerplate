"""Schema templates for code generation."""

SCHEMA_TEMPLATE = '''"""{app_name} schemas."""

from core.schemas.base_schema import CamelCaseSchema
from typing import Optional
from datetime import datetime


class {model_name}Schema(CamelCaseSchema):
    """Schema for {model_name} responses."""

    id: str
    name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class Create{model_name}Schema(CamelCaseSchema):
    """Schema for creating a {model_name}."""

    name: str
    description: str = ""


class Update{model_name}Schema(CamelCaseSchema):
    """Schema for updating a {model_name}."""

    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
'''

RBAC_SCHEMAS_TEMPLATE = '''"""RBAC schemas."""

from core.schemas.base_schema import CamelCaseSchema
from typing import List, Optional


class PermissionSchema(CamelCaseSchema):
    id: str
    name: str
    codename: str
    description: str
    content_type: Optional[str] = None


class RoleSchema(CamelCaseSchema):
    id: str
    name: str
    description: str
    permissions: List[PermissionSchema]
    is_default: bool


class UserRoleSchema(CamelCaseSchema):
    id: str
    role: RoleSchema
    content_type: Optional[str] = None
    object_id: Optional[int] = None
    is_global: bool


class AssignRoleSchema(CamelCaseSchema):
    role_id: str
    content_type: Optional[str] = None
    object_id: Optional[int] = None


class CreateRoleSchema(CamelCaseSchema):
    name: str
    description: str
    permission_ids: List[str] = []


class UpdateRoleSchema(CamelCaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[str]] = None


class CreatePermissionSchema(CamelCaseSchema):
    name: str
    codename: str
    description: str
    content_type: Optional[str] = None


class UserPermissionsSchema(CamelCaseSchema):
    user_id: str
    username: str
    permissions: List[str]
    roles: List[UserRoleSchema]


class BulkAssignPermissionsSchema(CamelCaseSchema):
    role_id: str
    permission_codenames: List[str]


class RoleStatsSchema(CamelCaseSchema):
    total_roles: int
    total_permissions: int
    users_with_roles: int
    default_role: Optional[str] = None
'''

CHAT_SCHEMAS_TEMPLATE = '''"""Chat schemas."""

from core.schemas.base_schema import CamelCaseSchema
from typing import List, Optional
from datetime import datetime


class MessageSchema(CamelCaseSchema):
    id: str
    content: str
    type: str
    sender_id: str
    sender_username: str
    conversation_id: str
    is_edited: bool
    reply_to_id: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    created_at: datetime
    edited_at: Optional[datetime] = None


class ConversationParticipantSchema(CamelCaseSchema):
    id: str
    user_id: str
    username: str
    email: str
    role: str
    is_active: bool
    joined_at: datetime
    left_at: Optional[datetime] = None
    unread_count: int
    last_read_at: datetime


class ConversationSchema(CamelCaseSchema):
    id: str
    title: str
    type: str
    description: str
    is_active: bool
    created_by_id: str
    created_by_username: str
    participant_count: int
    last_message_at: Optional[datetime] = None
    created_at: datetime
    participants: List[ConversationParticipantSchema] = []
    recent_messages: List[MessageSchema] = []


class CreateConversationSchema(CamelCaseSchema):
    title: str = ""
    type: str = "private"
    description: str = ""
    participant_user_ids: List[str] = []


class UpdateConversationSchema(CamelCaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CreateMessageSchema(CamelCaseSchema):
    content: str
    type: str = "text"
    reply_to_id: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None


class UpdateMessageSchema(CamelCaseSchema):
    content: str


class AddParticipantSchema(CamelCaseSchema):
    user_id: str
    role: str = "member"


class UpdateParticipantSchema(CamelCaseSchema):
    role: Optional[str] = None
    notifications_enabled: Optional[bool] = None


class MessageReactionSchema(CamelCaseSchema):
    id: str
    message_id: str
    user_id: str
    username: str
    emoji: str
    created_at: datetime


class AddReactionSchema(CamelCaseSchema):
    emoji: str


class ConversationListSchema(CamelCaseSchema):
    """Lightweight schema for conversation lists."""
    id: str
    title: str
    type: str
    participant_count: int
    unread_count: int
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    last_sender_username: Optional[str] = None


class ConversationStatsSchema(CamelCaseSchema):
    total_conversations: int
    active_conversations: int
    total_messages: int
    messages_today: int
    average_participants: float


class MessageSearchSchema(CamelCaseSchema):
    query: str
    conversation_id: Optional[str] = None
    sender_id: Optional[str] = None
    message_type: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class TypingIndicatorSchema(CamelCaseSchema):
    conversation_id: str
    user_id: str
    username: str
    is_typing: bool
'''

ORGANIZATION_SCHEMAS_TEMPLATE = '''"""Organization schemas."""

from core.schemas.base_schema import CamelCaseSchema
from typing import List, Optional
from datetime import datetime


class OrganizationSchema(CamelCaseSchema):
    id: str
    name: str
    slug: str
    description: str
    website: str
    email: str
    phone: str
    address: dict
    industry: str
    size: str
    is_active: bool
    is_verified: bool
    subscription_tier: str
    active_member_count: int
    admin_count: int
    created_at: datetime
    updated_at: datetime


class CreateOrganizationSchema(CamelCaseSchema):
    name: str
    description: str = ""
    website: str = ""
    email: str = ""
    phone: str = ""
    address: dict = {}
    industry: str = ""
    size: str = "startup"


class UpdateOrganizationSchema(CamelCaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[dict] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    is_active: Optional[bool] = None
    subscription_tier: Optional[str] = None


class OrganizationMemberSchema(CamelCaseSchema):
    id: str
    organization_id: str
    organization_name: str
    user_id: str
    username: str
    email: str
    role: str
    status: str
    invited_by_id: Optional[str] = None
    invited_by_username: Optional[str] = None
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None
    last_active_at: datetime
    is_admin: bool
    can_invite: bool
    can_manage_members: bool


class InviteMemberSchema(CamelCaseSchema):
    email: str
    role: str = "member"


class UpdateMemberRoleSchema(CamelCaseSchema):
    role: str


class UpdateMemberPermissionsSchema(CamelCaseSchema):
    permissions: dict


class OrganizationStatsSchema(CamelCaseSchema):
    total_members: int
    pending_invitations: int
    admin_count: int
    member_count: int
    active_projects: Optional[int] = None
    storage_used: Optional[int] = None
    api_calls_this_month: Optional[int] = None


class OrganizationListSchema(CamelCaseSchema):
    """Lightweight schema for organization lists."""
    id: str
    name: str
    slug: str
    description: str
    size: str
    active_member_count: int
    user_role: str
    last_active_at: datetime


class TransferOwnershipSchema(CamelCaseSchema):
    new_owner_user_id: str


class OrganizationInvitationSchema(CamelCaseSchema):
    id: str
    organization_name: str
    organization_slug: str
    invited_by_username: str
    role: str
    invited_at: datetime
    expires_at: datetime
    status: str


class BulkInviteSchema(CamelCaseSchema):
    emails: List[str]
    role: str = "member"
    send_email: bool = True


class OrganizationSettingsSchema(CamelCaseSchema):
    allow_member_invites: bool = True
    require_email_verification: bool = True
    auto_approve_members: bool = False
    default_member_role: str = "member"
    max_members: Optional[int] = None
    features_enabled: dict = {}


class UpdateOrganizationSettingsSchema(CamelCaseSchema):
    settings: dict
'''
