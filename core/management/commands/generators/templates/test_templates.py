"""Test templates for code generation."""

from core.management.commands.generators.codegen import (
    ResourceNames,
    from_import,
    import_block,
)

# Generated features get ONE smoke/permission test file. Playwright journeys in
# the frontend verify the feature itself; see docs/product/README.md.
API_ENDPOINT_TESTS_TEMPLATE = '''"""Smoke and permission tests for the {app_name} API."""

import pytest

{first_party_imports}


@pytest.mark.django_db
class Test{model_name}API:
    """Smoke and permission tests for {model_name} endpoints."""

    def test_list_as_owner_returns_200(self, authenticated_client):
        client, user = authenticated_client
        {model_name}.objects.create(user=user, title="Mine")
        response = client.get("/api/{route}/")
        assert response.status_code == 200

    def test_other_user_cannot_read_item(self, authenticated_client):
        client, _ = authenticated_client
        other = UserFactory()
        obj = {model_name}.objects.create(user=other, title="Theirs")
        response = client.get(f"/api/{route}/{{obj.id}}")
        assert response.status_code == 404

    def test_create_with_invalid_payload_returns_422(self, authenticated_client):
        client, _ = authenticated_client
        response = client.post("/api/{route}/", {{}}, content_type="application/json")
        assert_validation_error(response, field="title")
'''


def render_api_endpoint_tests(names: ResourceNames) -> str:
    """Render API_ENDPOINT_TESTS_TEMPLATE with its imports in isort order."""
    first_party_imports = import_block(
        "from core.tests.factories import UserFactory",
        from_import(f"{names.app_name}.models", names.model_name),
        "from tests.utils.assertions import assert_validation_error",
    )
    return API_ENDPOINT_TESTS_TEMPLATE.format(
        first_party_imports=first_party_imports, **names.context()
    )


RBAC_TESTS_TEMPLATE = '''"""RBAC tests."""

import pytest

from {app_name}.models import Role, Permission


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
from {app_name}.models import Conversation, Message

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
