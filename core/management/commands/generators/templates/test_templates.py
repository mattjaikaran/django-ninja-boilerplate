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


# Staff-only routes: staff 200/201/204, regular user 403 (read and write), the
# user's own permissions 200, invalid payload 422. Rendered with str.format.
RBAC_TESTS_TEMPLATE = '''"""Smoke and permission tests for the {app_name} API."""

import pytest
from ninja_jwt.tokens import RefreshToken

{first_party_imports}


@pytest.fixture
def staff_client(api_client, staff_user):
    token = RefreshToken.for_user(staff_user).access_token
    api_client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {{token}}"
    return api_client


@pytest.mark.django_db
class TestRBACAPI:
    """Staff manage roles; regular users read only their own permissions."""

    def test_staff_can_list_roles(self, staff_client):
        Role.objects.create(name="editor")
        response = staff_client.get("/api/rbac/roles")
        assert response.status_code == 200
        assert [role["name"] for role in response.json()] == ["editor"]

    def test_regular_user_cannot_list_roles(self, authenticated_client):
        client, _ = authenticated_client
        response = client.get("/api/rbac/roles")
        assert response.status_code == 403

    def test_regular_user_cannot_create_role(self, authenticated_client):
        client, _ = authenticated_client
        response = client.post(
            "/api/rbac/roles", {{"name": "admin"}}, content_type="application/json"
        )
        assert response.status_code == 403
        assert not Role.objects.filter(name="admin").exists()

    def test_user_reads_own_permissions(self, authenticated_client):
        client, user = authenticated_client
        UserRole.objects.create(user=user, role=Role.objects.create(name="viewer"))
        response = client.get("/api/rbac/me/permissions")
        assert response.status_code == 200
        roles = [item["role"]["name"] for item in response.json()["roles"]]
        assert roles == ["viewer"]

    def test_staff_creates_role_with_permissions(self, staff_client):
        permission = Permission.objects.create(name="Edit", codename="edit")
        response = staff_client.post(
            "/api/rbac/roles",
            {{"name": "editor", "permissionIds": [str(permission.id)]}},
            content_type="application/json",
        )
        assert response.status_code == 201
        codenames = [item["codename"] for item in response.json()["permissions"]]
        assert codenames == ["edit"]

    def test_staff_assigns_and_removes_role(self, staff_client, user):
        role = Role.objects.create(name="viewer")
        url = f"/api/rbac/users/{{user.id}}/roles"
        response = staff_client.post(
            url, {{"roleId": str(role.id)}}, content_type="application/json"
        )
        assert response.status_code == 201
        response = staff_client.delete(f"{{url}}/{{role.id}}")
        assert response.status_code == 204
        assert not UserRole.objects.filter(user=user).exists()

    def test_create_role_with_invalid_payload_returns_422(self, staff_client):
        response = staff_client.post(
            "/api/rbac/roles", {{}}, content_type="application/json"
        )
        assert_validation_error(response, field="name")
'''
