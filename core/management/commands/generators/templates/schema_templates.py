"""Schema templates for code generation."""

RBAC_SCHEMAS_TEMPLATE = '''"""RBAC schemas."""

from ninja import Schema
from typing import List, Optional


class PermissionSchema(Schema):
    id: str
    name: str
    codename: str
    description: str
    content_type: Optional[str] = None


class RoleSchema(Schema):
    id: str
    name: str
    description: str
    permissions: List[PermissionSchema]
    is_default: bool


class UserRoleSchema(Schema):
    id: str
    role: RoleSchema
    content_type: Optional[str] = None
    object_id: Optional[int] = None
    is_global: bool


class AssignRoleSchema(Schema):
    role_id: str
    content_type: Optional[str] = None
    object_id: Optional[int] = None


class CreateRoleSchema(Schema):
    name: str
    description: str
    permission_ids: List[str] = []


class UpdateRoleSchema(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[str]] = None


class CreatePermissionSchema(Schema):
    name: str
    codename: str
    description: str
    content_type: Optional[str] = None


class UserPermissionsSchema(Schema):
    user_id: str
    username: str
    permissions: List[str]
    roles: List[UserRoleSchema]


class BulkAssignPermissionsSchema(Schema):
    role_id: str
    permission_codenames: List[str]


class RoleStatsSchema(Schema):
    total_roles: int
    total_permissions: int
    users_with_roles: int
    default_role: Optional[str] = None
'''

CHAT_SCHEMAS_TEMPLATE = '''"""Chat schemas."""

from ninja import Schema
from typing import List, Optional
from datetime import datetime


class MessageSchema(Schema):
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


class ConversationParticipantSchema(Schema):
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


class ConversationSchema(Schema):
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


class CreateConversationSchema(Schema):
    title: str = ""
    type: str = "private"
    description: str = ""
    participant_user_ids: List[str] = []


class UpdateConversationSchema(Schema):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CreateMessageSchema(Schema):
    content: str
    type: str = "text"
    reply_to_id: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None


class UpdateMessageSchema(Schema):
    content: str


class AddParticipantSchema(Schema):
    user_id: str
    role: str = "member"


class UpdateParticipantSchema(Schema):
    role: Optional[str] = None
    notifications_enabled: Optional[bool] = None


class MessageReactionSchema(Schema):
    id: str
    message_id: str
    user_id: str
    username: str
    emoji: str
    created_at: datetime


class AddReactionSchema(Schema):
    emoji: str


class ConversationListSchema(Schema):
    """Lightweight schema for conversation lists."""
    id: str
    title: str
    type: str
    participant_count: int
    unread_count: int
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None
    last_sender_username: Optional[str] = None


class ConversationStatsSchema(Schema):
    total_conversations: int
    active_conversations: int
    total_messages: int
    messages_today: int
    average_participants: float


class MessageSearchSchema(Schema):
    query: str
    conversation_id: Optional[str] = None
    sender_id: Optional[str] = None
    message_type: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class TypingIndicatorSchema(Schema):
    conversation_id: str
    user_id: str
    username: str
    is_typing: bool
'''

ORGANIZATION_SCHEMAS_TEMPLATE = '''"""Organization schemas."""

from ninja import Schema
from typing import List, Optional
from datetime import datetime


class OrganizationSchema(Schema):
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


class CreateOrganizationSchema(Schema):
    name: str
    description: str = ""
    website: str = ""
    email: str = ""
    phone: str = ""
    address: dict = {}
    industry: str = ""
    size: str = "startup"


class UpdateOrganizationSchema(Schema):
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


class OrganizationMemberSchema(Schema):
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


class InviteMemberSchema(Schema):
    email: str
    role: str = "member"


class UpdateMemberRoleSchema(Schema):
    role: str


class UpdateMemberPermissionsSchema(Schema):
    permissions: dict


class OrganizationStatsSchema(Schema):
    total_members: int
    pending_invitations: int
    admin_count: int
    member_count: int
    active_projects: Optional[int] = None
    storage_used: Optional[int] = None
    api_calls_this_month: Optional[int] = None


class OrganizationListSchema(Schema):
    """Lightweight schema for organization lists."""
    id: str
    name: str
    slug: str
    description: str
    size: str
    active_member_count: int
    user_role: str
    last_active_at: datetime


class TransferOwnershipSchema(Schema):
    new_owner_user_id: str


class OrganizationInvitationSchema(Schema):
    id: str
    organization_name: str
    organization_slug: str
    invited_by_username: str
    role: str
    invited_at: datetime
    expires_at: datetime
    status: str


class BulkInviteSchema(Schema):
    emails: List[str]
    role: str = "member"
    send_email: bool = True


class OrganizationSettingsSchema(Schema):
    allow_member_invites: bool = True
    require_email_verification: bool = True
    auto_approve_members: bool = False
    default_member_role: str = "member"
    max_members: Optional[int] = None
    features_enabled: dict = {}


class UpdateOrganizationSettingsSchema(Schema):
    settings: dict
'''
