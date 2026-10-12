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


RBAC_SERVICE_TEMPLATE = '''"""RBAC permissions system."""

from typing import Any, Optional
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models

from .models import Role, Permission, UserRole

User = get_user_model()


class RBACService:
    """Service for RBAC operations."""

    @staticmethod
    def assign_role_to_user(
        user: User,
        role: Role,
        content_object: Optional[Any] = None
    ) -> UserRole:
        """Assign a role to a user, optionally scoped to an object."""
        content_type = None
        object_id = None

        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = content_object.pk

        user_role, created = UserRole.objects.get_or_create(
            user=user,
            role=role,
            content_type=content_type,
            object_id=object_id,
        )

        return user_role

    @staticmethod
    def remove_role_from_user(
        user: User,
        role: Role,
        content_object: Optional[Any] = None
    ) -> bool:
        """Remove a role from a user."""
        content_type = None
        object_id = None

        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = content_object.pk

        try:
            user_role = UserRole.objects.get(
                user=user,
                role=role,
                content_type=content_type,
                object_id=object_id,
            )
            user_role.delete()
            return True
        except UserRole.DoesNotExist:
            return False

    @staticmethod
    def user_has_permission(
        user: User,
        permission_codename: str,
        content_object: Optional[Any] = None
    ) -> bool:
        """Check if user has a specific permission."""
        if user.is_superuser:
            return True

        # Get all user roles
        user_roles = UserRole.objects.filter(user=user)

        # Filter by object if provided
        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            user_roles = user_roles.filter(
                models.Q(content_type=content_type, object_id=content_object.pk) |
                models.Q(content_type__isnull=True, object_id__isnull=True)  # Global roles
            )
        else:
            # For global permissions, only check global roles
            user_roles = user_roles.filter(
                content_type__isnull=True,
                object_id__isnull=True
            )

        # Check if any role has the permission
        for user_role in user_roles:
            if user_role.role.permissions.filter(codename=permission_codename).exists():
                return True

        return False

    @staticmethod
    def user_has_role(
        user: User,
        role_name: str,
        content_object: Optional[Any] = None
    ) -> bool:
        """Check if user has a specific role."""
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            return False

        content_type = None
        object_id = None

        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            object_id = content_object.pk

        return UserRole.objects.filter(
            user=user,
            role=role,
            content_type=content_type,
            object_id=object_id,
        ).exists()

    @staticmethod
    def get_user_permissions(
        user: User,
        content_object: Optional[Any] = None
    ) -> list[str]:
        """Get all permissions for a user."""
        if user.is_superuser:
            return ["*"]  # Superuser has all permissions

        # Get all user roles
        user_roles = UserRole.objects.filter(user=user).select_related("role")

        # Filter by object if provided
        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            user_roles = user_roles.filter(
                models.Q(content_type=content_type, object_id=content_object.pk) |
                models.Q(content_type__isnull=True, object_id__isnull=True)  # Global roles
            )
        else:
            # For global permissions, only check global roles
            user_roles = user_roles.filter(
                content_type__isnull=True,
                object_id__isnull=True
            )

        # Collect all permissions
        permissions = set()
        for user_role in user_roles:
            role_permissions = user_role.role.permissions.values_list("codename", flat=True)
            permissions.update(role_permissions)

        return list(permissions)

    @staticmethod
    def get_user_roles(
        user: User,
        content_object: Optional[Any] = None
    ) -> list[Role]:
        """Get all roles for a user."""
        user_roles = UserRole.objects.filter(user=user).select_related("role")

        if content_object:
            content_type = ContentType.objects.get_for_model(content_object)
            user_roles = user_roles.filter(
                models.Q(content_type=content_type, object_id=content_object.pk) |
                models.Q(content_type__isnull=True, object_id__isnull=True)
            )

        return [user_role.role for user_role in user_roles]

    @staticmethod
    def bulk_assign_permissions(role: Role, permission_codenames: list[str]) -> int:
        """Bulk assign permissions to a role."""
        permissions = Permission.objects.filter(codename__in=permission_codenames)
        role.permissions.set(permissions)
        return permissions.count()

    @staticmethod
    def create_default_roles_and_permissions():
        """Create default roles and permissions."""
        # Create basic permissions
        permissions_data = [
            ("view_user", "Can view users"),
            ("add_user", "Can add users"),
            ("change_user", "Can change users"),
            ("delete_user", "Can delete users"),
            ("view_content", "Can view content"),
            ("add_content", "Can add content"),
            ("change_content", "Can change content"),
            ("delete_content", "Can delete content"),
            ("manage_roles", "Can manage roles and permissions"),
            ("view_roles", "Can view roles"),
            ("view_permissions", "Can view permissions"),
            ("view_user_permissions", "Can view user permissions"),
        ]

        for codename, name in permissions_data:
            Permission.objects.get_or_create(
                codename=codename,
                defaults={"name": name}
            )

        # Create basic roles
        roles_data = [
            ("admin", "Administrator", ["manage_roles", "view_roles", "view_permissions", "view_user_permissions", "view_user", "add_user", "change_user", "delete_user"]),
            ("editor", "Editor", ["view_content", "add_content", "change_content"]),
            ("viewer", "Viewer", ["view_content"]),
            ("user", "Regular User", ["view_content"]),
        ]

        for role_name, description, permission_codenames in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={"description": description}
            )

            if created or role.permissions.count() == 0:
                permissions = Permission.objects.filter(codename__in=permission_codenames)
                role.permissions.set(permissions)

        # Set 'user' as default role
        try:
            user_role = Role.objects.get(name="user")
            user_role.is_default = True
            user_role.save()
        except Role.DoesNotExist:
            pass


# Decorator factory for permission checking
def permission_required(permission_codename: str, content_object_func=None):
    """Decorator factory for permission checking."""
    def decorator(func):
        def wrapper(self, request, *args, **kwargs):
            content_object = None
            if content_object_func:
                content_object = content_object_func(request, *args, **kwargs)

            if not RBACService.user_has_permission(request.user, permission_codename, content_object):
                from ninja_extra.exceptions import APIException
                raise APIException("Permission denied", 403)

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator


def role_required(role_name: str, content_object_func=None):
    """Decorator factory for role checking."""
    def decorator(func):
        def wrapper(self, request, *args, **kwargs):
            content_object = None
            if content_object_func:
                content_object = content_object_func(request, *args, **kwargs)

            if not RBACService.user_has_role(request.user, role_name, content_object):
                from ninja_extra.exceptions import APIException
                raise APIException("Role required", 403)

            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator
'''

ORGANIZATION_SERVICE_TEMPLATE = '''"""Organization service for business logic."""

from typing import List, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Organization, OrganizationMember

User = get_user_model()


class OrganizationService:
    """Service class for organization operations."""

    @staticmethod
    def create_organization(
        name: str,
        owner: User,
        description: str = "",
        **kwargs
    ) -> Organization:
        """Create a new organization with an owner."""
        with transaction.atomic():
            # Create the organization
            organization = Organization.objects.create(
                name=name,
                description=description,
                **kwargs
            )

            # Add owner as the first member
            OrganizationMember.objects.create(
                organization=organization,
                user=owner,
                role="owner",
                status="active",
                joined_at=timezone.now()
            )

            return organization

    @staticmethod
    def invite_member(
        organization: Organization,
        email: str,
        role: str,
        invited_by: User
    ) -> OrganizationMember:
        """Invite a user to join the organization."""
        # Check if inviter has permission
        inviter_member = OrganizationMember.objects.get(
            organization=organization,
            user=invited_by,
            status="active"
        )

        if not inviter_member.can_invite:
            raise ValidationError("You don't have permission to invite members")

        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Could send an invitation email to register
            raise ValidationError("User with this email does not exist")

        # Check if already a member
        if OrganizationMember.objects.filter(
            organization=organization,
            user=user
        ).exists():
            raise ValidationError("User is already a member of this organization")

        # Create invitation
        member = OrganizationMember.objects.create(
            organization=organization,
            user=user,
            role=role,
            status="pending",
            invited_by=invited_by,
            invited_at=timezone.now(),
            invitation_expires_at=timezone.now() + timezone.timedelta(days=7)
        )

        # TODO: Send invitation email

        return member

    @staticmethod
    def accept_invitation(member: OrganizationMember) -> bool:
        """Accept an organization invitation."""
        if member.status != "pending":
            return False

        if member.invitation_expires_at and member.invitation_expires_at < timezone.now():
            return False

        member.status = "active"
        member.joined_at = timezone.now()
        member.save()

        return True

    @staticmethod
    def remove_member(
        organization: Organization,
        user_to_remove: User,
        removed_by: User
    ) -> bool:
        """Remove a member from the organization."""
        # Check permissions
        remover_member = OrganizationMember.objects.get(
            organization=organization,
            user=removed_by,
            status="active"
        )

        member_to_remove = OrganizationMember.objects.get(
            organization=organization,
            user=user_to_remove
        )

        # Owner can remove anyone, admin can remove non-admins, users can remove themselves
        if (remover_member.is_owner or
            (remover_member.can_manage_members and not member_to_remove.is_admin) or
            user_to_remove == removed_by):

            member_to_remove.status = "inactive"
            member_to_remove.save()
            return True

        return False

    @staticmethod
    def update_member_role(
        organization: Organization,
        user_to_update: User,
        new_role: str,
        updated_by: User
    ) -> bool:
        """Update a member's role."""
        updater_member = OrganizationMember.objects.get(
            organization=organization,
            user=updated_by,
            status="active"
        )

        member_to_update = OrganizationMember.objects.get(
            organization=organization,
            user=user_to_update,
            status="active"
        )

        # Only owners can change roles, and can't demote themselves if they're the only owner
        if not updater_member.is_owner:
            return False

        if (user_to_update == updated_by and
            new_role != "owner" and
            organization.members.filter(role="owner", status="active").count() == 1):
            return False

        member_to_update.role = new_role
        member_to_update.save()
        return True

    @staticmethod
    def get_organization_stats(organization: Organization) -> dict:
        """Get organization statistics."""
        return {
            "total_members": organization.members.filter(status="active").count(),
            "pending_invitations": organization.members.filter(status="pending").count(),
            "admin_count": organization.members.filter(
                status="active",
                role__in=["owner", "admin"]
            ).count(),
            "member_count": organization.members.filter(
                status="active",
                role="member"
            ).count(),
        }

    @staticmethod
    def transfer_ownership(
        organization: Organization,
        new_owner: User,
        current_owner: User
    ) -> bool:
        """Transfer organization ownership."""
        # Verify current owner
        current_owner_member = OrganizationMember.objects.get(
            organization=organization,
            user=current_owner,
            role="owner",
            status="active"
        )

        # Verify new owner is a member
        new_owner_member = OrganizationMember.objects.get(
            organization=organization,
            user=new_owner,
            status="active"
        )

        with transaction.atomic():
            # Demote current owner to admin
            current_owner_member.role = "admin"
            current_owner_member.save()

            # Promote new owner
            new_owner_member.role = "owner"
            new_owner_member.save()

        return True

    @staticmethod
    def get_user_organizations(user: User) -> List[Organization]:
        """Get all organizations a user belongs to."""
        return Organization.objects.filter(
            members__user=user,
            members__status="active",
            is_active=True
        ).distinct()

    @staticmethod
    def can_user_access_organization(user: User, organization: Organization) -> bool:
        """Check if user can access an organization."""
        return OrganizationMember.objects.filter(
            organization=organization,
            user=user,
            status="active"
        ).exists()
'''
