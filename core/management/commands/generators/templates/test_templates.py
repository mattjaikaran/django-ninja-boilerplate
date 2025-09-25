"""Test templates for code generation."""

RBAC_TESTS_TEMPLATE = '''"""RBAC tests."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from {app_name}.models import Role, Permission, UserRole
from {app_name}.services.rbac_service import RBACService

User = get_user_model()


@pytest.fixture
def permission():
    return Permission.objects.create(
        name="Test Permission",
        codename="test_permission",
        description="A test permission"
    )


@pytest.fixture
def role(permission):
    role = Role.objects.create(
        name="Test Role",
        description="A test role"
    )
    role.permissions.add(permission)
    return role


@pytest.mark.django_db
class TestRBACModels:
    def test_create_permission(self):
        permission = Permission.objects.create(
            name="Test Permission",
            codename="test_permission"
        )
        assert str(permission) == "Test Permission"

    def test_create_role(self, permission):
        role = Role.objects.create(name="Test Role")
        role.permissions.add(permission)
        assert str(role) == "Test Role"
        assert role.permissions.count() == 1

    def test_create_user_role(self, test_user, role):
        user_role = UserRole.objects.create(user=test_user, role=role)
        assert str(user_role) == f"{{test_user.username}} - {{role.name}}"
        assert user_role.is_global


@pytest.mark.django_db
class TestRBACService:
    def test_assign_role_to_user(self, test_user, role):
        user_role = RBACService.assign_role_to_user(test_user, role)
        assert user_role.user == test_user
        assert user_role.role == role
        assert user_role.is_global

    def test_remove_role_from_user(self, test_user, role):
        RBACService.assign_role_to_user(test_user, role)
        success = RBACService.remove_role_from_user(test_user, role)
        assert success
        assert not UserRole.objects.filter(user=test_user, role=role).exists()

    def test_user_has_permission(self, test_user, role, permission):
        # User doesn't have permission initially
        assert not RBACService.user_has_permission(test_user, permission.codename)

        # Assign role and check permission
        RBACService.assign_role_to_user(test_user, role)
        assert RBACService.user_has_permission(test_user, permission.codename)

    def test_user_has_role(self, test_user, role):
        # User doesn't have role initially
        assert not RBACService.user_has_role(test_user, role.name)

        # Assign role and check
        RBACService.assign_role_to_user(test_user, role)
        assert RBACService.user_has_role(test_user, role.name)

    def test_get_user_permissions(self, test_user, role, permission):
        # User has no permissions initially
        permissions = RBACService.get_user_permissions(test_user)
        assert permission.codename not in permissions

        # Assign role and check permissions
        RBACService.assign_role_to_user(test_user, role)
        permissions = RBACService.get_user_permissions(test_user)
        assert permission.codename in permissions

    def test_superuser_has_all_permissions(self):
        superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password"
        )
        assert RBACService.user_has_permission(superuser, "any_permission")
        assert RBACService.get_user_permissions(superuser) == ["*"]


@pytest.mark.django_db
class TestRBACAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client
        return Client()

    def test_list_roles(self, api_client, role, auth_headers):
        response = api_client.get("/api/rbac/roles", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_create_role(self, api_client, permission, auth_headers):
        role_data = {{
            "name": "New Role",
            "description": "A new test role",
            "permission_ids": [str(permission.id)]
        }}
        response = api_client.post(
            "/api/rbac/roles",
            role_data,
            content_type="application/json",
            **auth_headers
        )
        assert response.status_code == 201
        assert Role.objects.filter(name="New Role").exists()
'''

CHAT_TESTS_TEMPLATE = '''"""Chat tests."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from {app_name}.models import Conversation, ConversationParticipant, Message, MessageReaction

User = get_user_model()


@pytest.fixture
def other_user():
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123"
    )


@pytest.fixture
def conversation(test_user, other_user):
    conversation = Conversation.objects.create(
        title="Test Chat",
        type="private",
        created_by=test_user
    )
    conversation.add_participant(test_user)
    conversation.add_participant(other_user)
    return conversation


@pytest.fixture
def message(conversation, test_user):
    return Message.objects.create(
        conversation=conversation,
        sender=test_user,
        content="Test message",
        type="text"
    )


@pytest.mark.django_db
class TestConversationModel:
    def test_create_conversation(self, test_user):
        conversation = Conversation.objects.create(
            title="Test Chat",
            type="private",
            created_by=test_user
        )
        assert str(conversation) == "Test Chat"
        assert conversation.type == "private"
        assert conversation.created_by == test_user

    def test_add_participant(self, conversation, test_user, other_user):
        assert conversation.participant_count == 2
        assert conversation.participants.filter(user=test_user, is_active=True).exists()
        assert conversation.participants.filter(user=other_user, is_active=True).exists()

    def test_remove_participant(self, conversation, other_user):
        success = conversation.remove_participant(other_user)
        assert success
        participant = conversation.participants.get(user=other_user)
        assert not participant.is_active
        assert participant.left_at is not None


@pytest.mark.django_db
class TestConversationParticipant:
    def test_unread_count(self, conversation, test_user, other_user):
        # Create some messages
        Message.objects.create(
            conversation=conversation,
            sender=other_user,
            content="Message 1"
        )
        Message.objects.create(
            conversation=conversation,
            sender=other_user,
            content="Message 2"
        )

        participant = conversation.participants.get(user=test_user)
        assert participant.unread_count == 2

        # Mark as read
        participant.mark_as_read()
        assert participant.unread_count == 0

    def test_participant_roles(self, conversation, test_user):
        participant = conversation.participants.get(user=test_user)
        participant.role = "admin"
        participant.save()

        assert participant.is_admin
        assert participant.can_invite


@pytest.mark.django_db
class TestMessage:
    def test_create_message(self, conversation, test_user):
        message = Message.objects.create(
            conversation=conversation,
            sender=test_user,
            content="Test message",
            type="text"
        )
        assert str(message) == f"Message from {{test_user.username}} in {{conversation}}"
        assert message.content == "Test message"
        assert message.type == "text"
        assert not message.is_edited

        # Check that conversation's last_message_at was updated
        conversation.refresh_from_db()
        assert conversation.last_message_at == message.created_at

    def test_reply_to_message(self, conversation, test_user, message):
        reply = Message.objects.create(
            conversation=conversation,
            sender=test_user,
            content="Reply to test message",
            reply_to=message
        )
        assert reply.reply_to == message
        assert reply in message.replies.all()

    def test_message_reactions(self, message, test_user):
        reaction = MessageReaction.objects.create(
            message=message,
            user=test_user,
            emoji="👍"
        )
        assert reaction.emoji == "👍"
        assert reaction in message.reactions.all()


@pytest.mark.django_db
class TestChatAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client
        return Client()

    def test_list_conversations(self, api_client, conversation, auth_headers):
        response = api_client.get("/api/conversations/", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["id"] == str(conversation.id)

    def test_create_conversation(self, api_client, test_user, other_user, auth_headers):
        conversation_data = {{
            "title": "New Chat",
            "type": "private",
            "description": "Test conversation",
            "participant_user_ids": [str(other_user.id)]
        }}
        response = api_client.post(
            "/api/conversations/",
            conversation_data,
            content_type="application/json",
            **auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Chat"
        assert Conversation.objects.filter(title="New Chat").exists()

    def test_send_message(self, api_client, conversation, auth_headers):
        message_data = {{
            "content": "Hello, world!",
            "type": "text"
        }}
        response = api_client.post(
            f"/api/messages/conversation/{{conversation.id}}/",
            message_data,
            content_type="application/json",
            **auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Hello, world!"
        assert Message.objects.filter(content="Hello, world!").exists()

    def test_list_messages(self, api_client, conversation, message, auth_headers):
        response = api_client.get(
            f"/api/messages/conversation/{{conversation.id}}/",
            **auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["content"] == message.content
'''

ORGANIZATION_TESTS_TEMPLATE = '''"""Organization tests."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from {app_name}.models import Organization, OrganizationMember
from {app_name}.services.organization_service import OrganizationService

User = get_user_model()


@pytest.fixture
def other_user():
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123"
    )


@pytest.fixture
def organization(test_user):
    return OrganizationService.create_organization(
        name="Test Organization",
        owner=test_user,
        description="A test organization"
    )


@pytest.fixture
def member(organization, other_user, test_user):
    return OrganizationService.invite_member(
        organization=organization,
        email=other_user.email,
        role="member",
        invited_by=test_user
    )


@pytest.mark.django_db
class TestOrganizationModel:
    def test_create_organization(self, test_user):
        organization = Organization.objects.create(
            name="Test Org",
            slug="test-org",
            description="Test organization"
        )
        assert str(organization) == "Test Org"
        assert organization.name == "Test Org"
        assert organization.is_active

    def test_organization_properties(self, organization):
        assert organization.active_member_count >= 1  # At least the owner
        assert organization.admin_count >= 1  # At least the owner

    def test_add_member(self, organization, other_user):
        member = organization.add_member(other_user, role="member")
        assert member.user == other_user
        assert member.organization == organization
        assert member.role == "member"

    def test_remove_member(self, organization, other_user):
        organization.add_member(other_user, role="member")
        success = organization.remove_member(other_user)
        assert success
        member = organization.members.get(user=other_user)
        assert member.status == "inactive"


@pytest.mark.django_db
class TestOrganizationMember:
    def test_member_properties(self, member):
        assert not member.is_admin
        assert not member.can_manage_members
        assert member.can_invite is False  # Default member can't invite

    def test_admin_member(self, organization, other_user, test_user):
        admin_member = OrganizationService.invite_member(
            organization=organization,
            email=other_user.email,
            role="admin",
            invited_by=test_user
        )
        assert admin_member.is_admin
        assert admin_member.can_manage_members
        assert admin_member.can_invite

    def test_owner_member(self, organization, test_user):
        owner_member = organization.members.get(user=test_user)
        assert owner_member.is_owner
        assert owner_member.can_manage_members


@pytest.mark.django_db
class TestOrganizationService:
    def test_create_organization_with_owner(self, test_user):
        org = OrganizationService.create_organization(
            name="Service Test Org",
            owner=test_user,
            description="Created via service"
        )

        assert org.name == "Service Test Org"
        assert org.members.filter(user=test_user, role="owner").exists()

    def test_invite_member(self, organization, other_user, test_user):
        member = OrganizationService.invite_member(
            organization=organization,
            email=other_user.email,
            role="member",
            invited_by=test_user
        )

        assert member.user == other_user
        assert member.status == "pending"
        assert member.invited_by == test_user

    def test_accept_invitation(self, member):
        success = OrganizationService.accept_invitation(member)
        assert success

        member.refresh_from_db()
        assert member.status == "active"
        assert member.joined_at is not None

    def test_transfer_ownership(self, organization, other_user, test_user):
        # First add other user as member
        organization.add_member(other_user, role="admin")

        success = OrganizationService.transfer_ownership(
            organization=organization,
            new_owner=other_user,
            current_owner=test_user
        )

        assert success

        # Check ownership transfer
        old_owner = organization.members.get(user=test_user)
        new_owner = organization.members.get(user=other_user)

        assert old_owner.role == "admin"
        assert new_owner.role == "owner"

    def test_get_organization_stats(self, organization):
        stats = OrganizationService.get_organization_stats(organization)

        assert "total_members" in stats
        assert "pending_invitations" in stats
        assert "admin_count" in stats
        assert "member_count" in stats
        assert stats["total_members"] >= 1


@pytest.mark.django_db
class TestOrganizationAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client
        return Client()

    def test_list_user_organizations(self, api_client, organization, auth_headers):
        response = api_client.get("/api/organizations/", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["id"] == str(organization.id)

    def test_create_organization(self, api_client, auth_headers):
        org_data = {{
            "name": "API Test Org",
            "description": "Created via API",
            "industry": "technology",
            "size": "startup"
        }}
        response = api_client.post(
            "/api/organizations/",
            org_data,
            content_type="application/json",
            **auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "API Test Org"
        assert Organization.objects.filter(name="API Test Org").exists()

    def test_invite_member(self, api_client, organization, other_user, auth_headers):
        invite_data = {{
            "email": other_user.email,
            "role": "member"
        }}
        response = api_client.post(
            f"/api/organizations/{{organization.id}}/members/invite",
            invite_data,
            content_type="application/json",
            **auth_headers
        )
        assert response.status_code == 201
        assert OrganizationMember.objects.filter(
            organization=organization,
            user=other_user
        ).exists()
'''
