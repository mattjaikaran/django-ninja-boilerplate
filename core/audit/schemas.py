"""Pydantic Schemas for Audit Log API.

Defines request and response schemas for the audit log API endpoints.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from core.schemas.base_schema import CamelCaseSchema

# Values match core.audit.models.AuditAction.
AuditActionValue = Literal[
    "CREATE",
    "UPDATE",
    "DELETE",
    "SOFT_DELETE",
    "RESTORE",
    "LOGIN",
    "LOGOUT",
    "LOGIN_FAILED",
    "PASSWORD_CHANGE",
    "PASSWORD_RESET",
    "API_REQUEST",
    "PERMISSION_CHANGE",
    "EXPORT",
    "IMPORT",
    "CUSTOM",
]


class AuditLogSchema(CamelCaseSchema):
    """Schema for audit log responses."""

    id: str
    action: AuditActionValue
    action_description: str
    user_email: str
    model_name: str
    object_id: str
    object_repr: str
    changes: dict[str, Any]  # schema-ok: free-form audit diff
    previous_state: dict[str, Any]  # schema-ok: free-form audit snapshot
    new_state: dict[str, Any]  # schema-ok: free-form audit snapshot
    ip_address: str | None
    user_agent: str
    request_method: str
    request_path: str
    request_id: str
    timestamp: datetime
    extra_data: dict[str, Any]  # schema-ok: free-form audit context
    success: bool
    error_message: str

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string."""
        if isinstance(v, UUID):
            return str(v)
        return v


class AuditLogListSchema(CamelCaseSchema):
    """Minimal schema for audit log list responses."""

    id: str
    action: AuditActionValue
    action_description: str
    user_email: str
    model_name: str
    object_id: str
    timestamp: datetime
    success: bool

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string."""
        if isinstance(v, UUID):
            return str(v)
        return v


class AuditLogFilterSchema(CamelCaseSchema):
    """Schema for filtering audit logs."""

    action: AuditActionValue | None = Field(None, description="Filter by action type")
    user_email: str | None = Field(
        None, max_length=254, description="Filter by user email"
    )
    model_name: str | None = Field(
        None, max_length=255, description="Filter by model name"
    )
    object_id: str | None = Field(
        None, max_length=255, description="Filter by object ID"
    )
    ip_address: str | None = Field(
        None, max_length=39, description="Filter by IP address"
    )
    success: bool | None = Field(None, description="Filter by success status")
    start_date: datetime | None = Field(None, description="Filter logs from this date")
    end_date: datetime | None = Field(None, description="Filter logs until this date")
    search: str | None = Field(None, description="Search in description and paths")


class AuditLogDateRangeSchema(CamelCaseSchema):
    """Date window covered by audit log statistics."""

    start: str
    end: str
    days: int


class AuditLogStatsSchema(CamelCaseSchema):
    """Schema for audit log statistics."""

    total_logs: int
    logs_by_action: dict[str, int]
    logs_by_model: dict[str, int]
    logs_by_success: dict[str, int]
    recent_failed_logins: int
    unique_users: int
    unique_ips: int
    date_range: AuditLogDateRangeSchema


class AuditLogExportSchema(CamelCaseSchema):
    """Schema for audit log export request."""

    format: Literal["json", "csv"] = Field("json", description="Export format")
    start_date: datetime | None = None
    end_date: datetime | None = None
    actions: list[AuditActionValue] | None = Field(
        None, description="Filter by action types"
    )
    model_names: list[str] | None = Field(None, description="Filter by model names")


class AuditLogExportResponseSchema(CamelCaseSchema):
    """Schema for audit log export response."""

    download_url: str | None = None
    total_records: int
    format: Literal["json", "csv"]
    message: str
