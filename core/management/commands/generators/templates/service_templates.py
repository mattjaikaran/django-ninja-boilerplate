"""Service templates for code generation."""

from core.management.commands.generators.codegen import (
    ResourceNames,
    from_import,
    method_def,
)

# Owner-scoped CRUD service behind CONTROLLER_TEMPLATE. Every query filters on
# the owner, so another user's item is a 404.
SERVICE_TEMPLATE = '''"""Business logic for {model_name}. Every query is scoped to the owner."""

from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from {app_name}.models import {model_name}
{schema_import}


class {model_name}Service:
    """Owner-scoped CRUD for {model_name}."""

    def list_for_user(self, user: Any) -> QuerySet[{model_name}]:
        """Return the items that belong to the user, newest first."""
        return {model_name}.objects.filter(user=user).order_by("-created_at")

    def get_for_user(self, item_id: UUID, user: Any) -> {model_name}:
        """Return one item owned by the user. Raise Http404 for any other item."""
        return get_object_or_404({model_name}, id=item_id, user=user)

{create_def}
        """Create an item owned by the user."""
        return {model_name}.objects.create(user=user, **payload.model_dump())

{update_def}
        """Apply the set fields of the payload to an item owned by the user."""
        item = self.get_for_user(item_id, user)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        item.save()
        return item

    def delete(self, item_id: UUID, user: Any) -> None:
        """Delete an item owned by the user."""
        self.get_for_user(item_id, user).delete()
'''


def render_service(names: ResourceNames) -> str:
    """Render SERVICE_TEMPLATE for one resource."""
    model = names.model_name
    schema_import = from_import(
        f"{names.app_name}.schemas", f"Create{model}Schema", f"Update{model}Schema"
    )
    return SERVICE_TEMPLATE.format(
        schema_import=schema_import,
        create_def=method_def(
            "create", f"self, user: Any, payload: Create{model}Schema", model
        ),
        update_def=method_def(
            "update",
            f"self, item_id: UUID, user: Any, payload: Update{model}Schema",
            model,
        ),
        **names.context(),
    )


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
