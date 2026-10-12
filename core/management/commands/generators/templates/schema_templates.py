"""Schema templates for code generation."""

SCHEMA_TEMPLATE = '''"""{model_name} schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import field_validator

from core.schemas.base_schema import CamelCaseSchema


class {model_name}Schema(CamelCaseSchema):
    id: str
    title: str
    description: str
    created_at: str
    updated_at: str

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Serialize the UUID primary key as a string."""
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_datetime_to_str(cls, v):
        """Serialize timestamps as ISO 8601 strings."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class Create{model_name}Schema(CamelCaseSchema):
    title: str
    description: str


class Update{model_name}Schema(CamelCaseSchema):
    title: str
    description: str
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
