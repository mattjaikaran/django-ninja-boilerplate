"""Model templates for code generation."""

# Owned resource behind SERVICE_TEMPLATE: the service scopes every query on
# the ``user`` foreign key.
MODEL_TEMPLATE = '''"""{model_name} model."""

from django.conf import settings
from django.db import models

from core.models import AbstractBaseModel


class {model_name}(AbstractBaseModel):
    """A {model_snake} owned by one user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="{route}"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "{model_name}"
        verbose_name_plural = "{tag}"

    def __str__(self):
        return self.title
'''

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
