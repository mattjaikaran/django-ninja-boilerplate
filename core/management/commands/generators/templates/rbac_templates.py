"""RBAC generator templates."""

# RBAC catalog (Permission, Role) plus per-user assignments. Written verbatim:
# the models import nothing from the app.
RBAC_MODELS_TEMPLATE = '''"""RBAC models."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import AbstractBaseModel


class Permission(AbstractBaseModel):
    """A named capability that roles grant."""

    name = models.CharField(max_length=255, unique=True)
    codename = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(app_label)s_permissions",
        help_text="The content type this permission applies to",
    )

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Role(AbstractBaseModel):
    """A set of permissions assigned to users."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission, through="RolePermission", related_name="roles"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this role is assigned to new users by default",
    )

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RolePermission(AbstractBaseModel):
    """Through model for the Role-Permission relationship."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Role Permission"
        verbose_name_plural = "Role Permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="%(app_label)s_unique_role_permission",
            ),
        ]

    def __str__(self):
        return f"{self.role} - {self.permission}"


class UserRole(AbstractBaseModel):
    """A role assigned to a user, globally or on one object."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_roles"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    # Object-level scope. Both empty means a global assignment. object_id is
    # text so it holds UUID and integer primary keys.
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Content type for object-level permissions",
    )
    object_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Object ID for object-level permissions",
    )
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        verbose_name = "User Role"
        verbose_name_plural = "User Roles"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "content_type", "object_id"],
                name="%(app_label)s_unique_user_role_object",
            ),
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=models.Q(content_type__isnull=True, object_id__isnull=True),
                name="%(app_label)s_unique_global_user_role",
            ),
        ]

    def __str__(self):
        if self.is_global:
            return f"{self.user} - {self.role}"
        return f"{self.user} - {self.role} on {self.content_type}:{self.object_id}"

    @property
    def is_global(self):
        """Return True for an assignment without an object scope."""
        return self.content_type_id is None and self.object_id is None
'''

# Written verbatim: the schemas import nothing from the app.
RBAC_SCHEMAS_TEMPLATE = '''"""RBAC schemas."""

from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator, Field

from core.schemas.base_schema import CamelCaseSchema

# Serialize UUID primary keys as strings.
IdStr = Annotated[str, BeforeValidator(str)]


class PermissionSchema(CamelCaseSchema):
    id: IdStr
    name: str
    codename: str
    description: str
    content_type_id: int | None = None


class CreatePermissionSchema(CamelCaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    codename: str = Field(..., max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    description: str = ""


class RoleSchema(CamelCaseSchema):
    id: IdStr
    name: str
    description: str
    is_default: bool
    permissions: list[PermissionSchema]


class CreateRoleSchema(CamelCaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    is_default: bool = False
    permission_ids: list[UUID] = Field(default_factory=list)


class UpdateRoleSchema(CamelCaseSchema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_default: bool | None = None
    permission_ids: list[UUID] | None = None


class UserRoleSchema(CamelCaseSchema):
    id: IdStr
    role: RoleSchema
    content_type_id: int | None = None
    object_id: str | None = None
    is_global: bool


class AssignRoleSchema(CamelCaseSchema):
    role_id: UUID


class UserPermissionsSchema(CamelCaseSchema):
    user_id: IdStr
    permissions: list[str]
    roles: list[UserRoleSchema]
'''

# Rendered with str.format: {first_party_imports} is the app's isort block, so
# literal braces in the generated code are doubled.
RBAC_SERVICE_TEMPLATE = '''"""RBAC business logic.

Role and permission management acts on every user, so it is staff-only: the
controller requires IsAdminUser for those routes. Permission checks and
summaries are scoped to the user passed in.
"""

from typing import Any
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404

{first_party_imports}

DEFAULT_PERMISSIONS = [
    ("view_user", "Can view users"),
    ("add_user", "Can add users"),
    ("change_user", "Can change users"),
    ("delete_user", "Can delete users"),
    ("view_content", "Can view content"),
    ("add_content", "Can add content"),
    ("change_content", "Can change content"),
    ("delete_content", "Can delete content"),
    ("manage_roles", "Can manage roles and permissions"),
]

# (name, description, permission codenames). New users get "user".
DEFAULT_ROLES = [
    (
        "admin",
        "Administrator",
        ["manage_roles", "view_user", "add_user", "change_user", "delete_user"],
    ),
    ("editor", "Editor", ["view_content", "add_content", "change_content"]),
    ("viewer", "Viewer", ["view_content"]),
    ("user", "Regular User", ["view_content"]),
]
DEFAULT_ROLE = "user"


class RBACService:
    """Role and permission catalog, assignments and per-user checks."""

    # Catalog and assignments: staff-only callers.

    def list_roles(self) -> QuerySet[Role]:
        """Return every role with its permissions."""
        return Role.objects.prefetch_related("permissions").order_by("name")

    def list_permissions(self) -> QuerySet[Permission]:
        """Return every permission."""
        return Permission.objects.order_by("name")

    def create_permission(self, payload: CreatePermissionSchema) -> Permission:
        """Create a permission. Raise ConflictError for a duplicate."""
        duplicate = Q(name=payload.name) | Q(codename=payload.codename)
        if Permission.objects.filter(duplicate).exists():
            raise ConflictError("A permission with this name or codename exists")
        return Permission.objects.create(
            name=payload.name,
            codename=payload.codename,
            description=payload.description,
        )

    def create_role(self, payload: CreateRoleSchema) -> Role:
        """Create a role with the given permissions."""
        if Role.objects.filter(name=payload.name).exists():
            raise ConflictError("A role with this name exists")
        permissions = self._get_permissions(payload.permission_ids)
        with transaction.atomic():
            role = Role.objects.create(
                name=payload.name,
                description=payload.description,
                is_default=payload.is_default,
            )
            role.permissions.set(permissions)
        return role

    def update_role(self, role_id: UUID, payload: UpdateRoleSchema) -> Role:
        """Apply the set fields of the payload to a role."""
        role = get_object_or_404(Role, id=role_id)
        name_taken = Role.objects.filter(name=payload.name).exclude(id=role.id)
        if payload.name is not None and name_taken.exists():
            raise ConflictError("A role with this name exists")
        permissions = None
        if payload.permission_ids is not None:
            permissions = self._get_permissions(payload.permission_ids)
        with transaction.atomic():
            for field in payload.model_fields_set - {{"permission_ids"}}:
                value = getattr(payload, field)
                if value is not None:
                    setattr(role, field, value)
            role.save()
            if permissions is not None:
                role.permissions.set(permissions)
        return role

    def delete_role(self, role_id: UUID) -> None:
        """Delete a role and its assignments."""
        get_object_or_404(Role, id=role_id).delete()

    def assign_role(
        self, user_id: UUID, role_id: UUID, content_object: Any = None
    ) -> UserRole:
        """Assign a role to a user, globally or on one object."""
        user = get_object_or_404(get_user_model(), id=user_id)
        role = get_object_or_404(Role, id=role_id)
        user_role, _ = UserRole.objects.get_or_create(
            user=user, role=role, **self._scope(content_object)
        )
        return user_role

    def remove_role(
        self, user_id: UUID, role_id: UUID, content_object: Any = None
    ) -> None:
        """Remove a role assignment. Raise Http404 when it does not exist."""
        get_object_or_404(
            UserRole, user_id=user_id, role_id=role_id, **self._scope(content_object)
        ).delete()

    def get_user_summary(self, user_id: UUID) -> dict[str, Any]:
        """Return the roles and permissions of any user."""
        return self.permissions_summary(get_object_or_404(get_user_model(), id=user_id))

    def create_default_roles_and_permissions(self) -> None:
        """Create DEFAULT_PERMISSIONS and DEFAULT_ROLES that do not exist yet."""
        with transaction.atomic():
            for codename, name in DEFAULT_PERMISSIONS:
                Permission.objects.get_or_create(
                    codename=codename, defaults={{"name": name}}
                )
            for name, description, codenames in DEFAULT_ROLES:
                role, created = Role.objects.get_or_create(
                    name=name,
                    defaults={{
                        "description": description,
                        "is_default": name == DEFAULT_ROLE,
                    }},
                )
                if created:
                    role.permissions.set(
                        Permission.objects.filter(codename__in=codenames)
                    )

    # Checks scoped to the user passed in.

    def permissions_summary(self, user: Any) -> dict[str, Any]:
        """Return the user's global roles and permission codenames."""
        return {{
            "user_id": user.id,
            "permissions": self.get_user_permissions(user),
            "roles": list(self.get_user_roles(user)),
        }}

    def user_has_permission(
        self, user: Any, codename: str, content_object: Any = None
    ) -> bool:
        """Return True if one of the user's roles grants the permission."""
        if user.is_superuser:
            return True
        roles = self._user_roles(user, content_object)
        return roles.filter(role__permissions__codename=codename).exists()

    def user_has_role(
        self, user: Any, role_name: str, content_object: Any = None
    ) -> bool:
        """Return True if the user holds the role globally or on the object."""
        roles = self._user_roles(user, content_object)
        return roles.filter(role__name=role_name).exists()

    def get_user_permissions(self, user: Any, content_object: Any = None) -> list[str]:
        """Return the permission codenames of the user. A superuser gets ["*"]."""
        if user.is_superuser:
            return ["*"]
        codenames = (
            self._user_roles(user, content_object)
            .filter(role__permissions__isnull=False)
            .values_list("role__permissions__codename", flat=True)
            .distinct()
        )
        return sorted(codenames)

    def get_user_roles(
        self, user: Any, content_object: Any = None
    ) -> QuerySet[UserRole]:
        """Return the user's role assignments with their roles and permissions."""
        return (
            self._user_roles(user, content_object)
            .select_related("role")
            .prefetch_related("role__permissions")
        )

    def _user_roles(self, user: Any, content_object: Any) -> QuerySet[UserRole]:
        """Return global assignments, plus assignments on content_object if given."""
        roles = UserRole.objects.filter(user=user)
        is_global = Q(content_type__isnull=True, object_id__isnull=True)
        if content_object is None:
            return roles.filter(is_global)
        return roles.filter(is_global | Q(**self._scope(content_object)))

    @staticmethod
    def _scope(content_object: Any) -> dict[str, Any]:
        """Return the content_type/object_id lookup for an assignment scope."""
        if content_object is None:
            return {{"content_type": None, "object_id": None}}
        return {{
            "content_type": ContentType.objects.get_for_model(content_object),
            "object_id": str(content_object.pk),
        }}

    @staticmethod
    def _get_permissions(permission_ids: list[UUID]) -> list[Permission]:
        """Return the permissions. Raise ValidationError for an unknown id."""
        permissions = list(Permission.objects.filter(id__in=permission_ids))
        if len(permissions) != len(set(permission_ids)):
            raise ValidationError("One or more permission ids do not exist")
        return permissions
'''

# Staff-only RBAC management (IsAdminUser on the controller). The one route a
# regular user may call is GET /me/permissions, for their own roles. Rendered
# with str.format, so literal braces are doubled.
RBAC_CONTROLLER_TEMPLATE = '''"""RBAC controller. Staff manage roles; each user reads their own permissions."""

from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/rbac", tags=["RBAC"], auth=JWTAuth(), permissions=[IsAdminUser])
class RBACController:
    """Role and permission management.

    Every route is staff-only (IsAdminUser) except GET /me/permissions, which
    any authenticated user calls for their own roles and permissions. Put
    static paths before the first dynamic handler.
    """

    def __init__(self):
        self.service = RBACService()

    @http_get(
        "/me/permissions",
        response={{200: UserPermissionsSchema}},
        permissions=[IsAuthenticated],
    )
    @log_api_call()
    def get_my_permissions(self, request):
        """Get the authenticated user's roles and permissions."""
        return 200, self.service.permissions_summary(request.user)

    @http_get("/roles", response={{200: list[RoleSchema]}})
    @log_api_call()
    def list_roles(self, request):
        """List every role with its permissions."""
        return 200, self.service.list_roles()

    @http_post("/roles", response={{201: RoleSchema, 400: dict, 409: dict}})
    @log_api_call(include_payload=True)
    def create_role(self, request, payload: CreateRoleSchema):
        """Create a role."""
        return 201, self.service.create_role(payload)

    @http_get("/permissions", response={{200: list[PermissionSchema]}})
    @log_api_call()
    def list_permissions(self, request):
        """List every permission."""
        return 200, self.service.list_permissions()

    @http_post("/permissions", response={{201: PermissionSchema, 409: dict}})
    @log_api_call(include_payload=True)
    def create_permission(self, request, payload: CreatePermissionSchema):
        """Create a permission."""
        return 201, self.service.create_permission(payload)

    @http_put(
        "/roles/{{role_id}}",
        response={{200: RoleSchema, 400: dict, 404: dict, 409: dict}},
    )
    @log_api_call(include_payload=True)
    def update_role(self, request, role_id: UUID, payload: UpdateRoleSchema):
        """Update a role."""
        return 200, self.service.update_role(role_id, payload)

    @http_delete("/roles/{{role_id}}", response={{204: None, 404: dict}})
    @log_api_call()
    def delete_role(self, request, role_id: UUID):
        """Delete a role."""
        self.service.delete_role(role_id)
        return 204, None

    @http_get(
        "/users/{{user_id}}/permissions",
        response={{200: UserPermissionsSchema, 404: dict}},
    )
    @log_api_call()
    def get_user_permissions(self, request, user_id: UUID):
        """Get a user's roles and permissions."""
        return 200, self.service.get_user_summary(user_id)

    @http_post("/users/{{user_id}}/roles", response={{201: UserRoleSchema, 404: dict}})
    @log_api_call(include_payload=True)
    def assign_role(self, request, user_id: UUID, payload: AssignRoleSchema):
        """Assign a global role to a user."""
        return 201, self.service.assign_role(user_id, payload.role_id)

    @http_delete("/users/{{user_id}}/roles/{{role_id}}", response={{204: None, 404: dict}})
    @log_api_call()
    def remove_role(self, request, user_id: UUID, role_id: UUID):
        """Remove a global role from a user."""
        self.service.remove_role(user_id, role_id)
        return 204, None
'''

# Rendered with str.format: {first_party_imports} imports the app's models.
RBAC_ADMIN_TEMPLATE = '''"""RBAC admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

{first_party_imports}


class RolePermissionInline(TabularInline):
    model = RolePermission
    extra = 0


@admin.register(Permission)
class PermissionAdmin(ModelAdmin):
    list_display = ["name", "codename", "content_type", "created_at"]
    list_filter = ["content_type", "created_at"]
    search_fields = ["name", "codename", "description"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Role)
class RoleAdmin(ModelAdmin):
    list_display = ["name", "is_default", "permission_count", "created_at"]
    list_filter = ["is_default", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [RolePermissionInline]

    @admin.display(description="Permissions")
    def permission_count(self, obj):
        return obj.permissions.count()


@admin.register(UserRole)
class UserRoleAdmin(ModelAdmin):
    list_display = [
        "user",
        "role",
        "content_type",
        "object_id",
        "is_global",
        "created_at",
    ]
    list_filter = ["role", "content_type", "created_at"]
    search_fields = ["user__email", "role__name"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(boolean=True, description="Global")
    def is_global(self, obj):
        return obj.is_global


@admin.register(RolePermission)
class RolePermissionAdmin(ModelAdmin):
    list_display = ["role", "permission", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["role__name", "permission__name"]
    readonly_fields = ["created_at", "updated_at"]
'''

# Rendered with str.format: {first_party_imports} is the app's isort block, so
# literal braces in the generated code are doubled. Staff and superuser checks
# use IsAdminUser and IsSuperUser from api.permissions instead.
RBAC_DECORATORS_TEMPLATE = '''"""RBAC decorators for controller routes.

Put them below the @http_* decorator of a route on a JWTAuth controller.
get_object(request, *args, **kwargs) returns the object for an object-level
check.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

{first_party_imports}

Check = Callable[[RBACService, Any, Any], bool]


def _require(check: Check, message: str, get_object: Callable | None) -> Callable:
    """Return a decorator that raises APIPermissionError when check fails."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise AuthenticationError
            content_object = (
                get_object(request, *args, **kwargs) if get_object else None
            )
            if not check(RBACService(), request.user, content_object):
                raise APIPermissionError(message)
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator


def require_permission(codename: str, get_object: Callable | None = None) -> Callable:
    """Require one permission."""
    return _require(
        lambda service, user, obj: service.user_has_permission(user, codename, obj),
        "Permission denied",
        get_object,
    )


def require_role(role_name: str, get_object: Callable | None = None) -> Callable:
    """Require one role."""
    return _require(
        lambda service, user, obj: service.user_has_role(user, role_name, obj),
        "Role required",
        get_object,
    )


def require_any_permission(
    *codenames: str, get_object: Callable | None = None
) -> Callable:
    """Require at least one of the permissions."""
    return _require(
        lambda service, user, obj: any(
            service.user_has_permission(user, codename, obj) for codename in codenames
        ),
        "Permission denied",
        get_object,
    )


def require_all_permissions(
    *codenames: str, get_object: Callable | None = None
) -> Callable:
    """Require every one of the permissions."""
    return _require(
        lambda service, user, obj: all(
            service.user_has_permission(user, codename, obj) for codename in codenames
        ),
        "Permission denied",
        get_object,
    )
'''

# Rendered with str.format: {first_party_imports} imports RBACService.
RBAC_MIDDLEWARE_TEMPLATE = '''"""RBAC middleware: permission helpers on request.user."""

from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin

{first_party_imports}


class RBACMiddleware(MiddlewareMixin):
    """Add has_permission, has_role and get_permissions to request.user.

    Middleware runs before the API authenticates a JWT bearer token, so the
    helpers exist only for session-authenticated requests.
    """

    def process_request(self, request: HttpRequest) -> None:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return
        service = RBACService()
        user.has_permission = lambda codename, obj=None: service.user_has_permission(
            user, codename, obj
        )
        user.has_role = lambda role_name, obj=None: service.user_has_role(
            user, role_name, obj
        )
        user.get_permissions = lambda obj=None: service.get_user_permissions(user, obj)
'''

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
