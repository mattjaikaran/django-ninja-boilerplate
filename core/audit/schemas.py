"""Pydantic Schemas for Audit Log API.

Defines request and response schemas for the audit log API endpoints.
"""

from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import Field, field_validator


class AuditLogSchema(Schema):
    """Schema for audit log responses."""

    id: str
    action: str
    action_description: str
    user_email: str
    model_name: str
    object_id: str
    object_repr: str
    changes: dict
    previous_state: dict
    new_state: dict
    ip_address: str | None
    user_agent: str
    request_method: str
    request_path: str
    request_id: str
    timestamp: datetime
    extra_data: dict
    success: bool
    error_message: str

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string."""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True


class AuditLogListSchema(Schema):
    """Minimal schema for audit log list responses."""

    id: str
    action: str
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

    class Config:
        from_attributes = True


class AuditLogFilterSchema(Schema):
    """Schema for filtering audit logs."""

    action: str | None = Field(None, description="Filter by action type")
    user_email: str | None = Field(None, description="Filter by user email")
    model_name: str | None = Field(None, description="Filter by model name")
    object_id: str | None = Field(None, description="Filter by object ID")
    ip_address: str | None = Field(None, description="Filter by IP address")
    success: bool | None = Field(None, description="Filter by success status")
    start_date: datetime | None = Field(None, description="Filter logs from this date")
    end_date: datetime | None = Field(None, description="Filter logs until this date")
    search: str | None = Field(None, description="Search in description and paths")


class AuditLogStatsSchema(Schema):
    """Schema for audit log statistics."""

    total_logs: int
    logs_by_action: dict
    logs_by_model: dict
    logs_by_success: dict
    recent_failed_logins: int
    unique_users: int
    unique_ips: int
    date_range: dict


class AuditLogExportSchema(Schema):
    """Schema for audit log export request."""

    format: str = Field("json", description="Export format: json, csv")
    start_date: datetime | None = None
    end_date: datetime | None = None
    actions: list[str] | None = Field(None, description="Filter by action types")
    model_names: list[str] | None = Field(None, description="Filter by model names")


class AuditLogExportResponseSchema(Schema):
    """Schema for audit log export response."""

    download_url: str | None = None
    total_records: int
    format: str
    message: str
