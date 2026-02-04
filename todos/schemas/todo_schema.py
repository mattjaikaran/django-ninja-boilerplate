from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import field_validator


class TodoSchema(Schema):
    id: str
    user: str
    title: str
    description: str
    completed: bool
    priority: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string."""
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator("user", mode="before")
    @classmethod
    def convert_user_to_str(cls, v):
        """Convert User object to string (user id)."""
        if hasattr(v, "id"):
            return str(v.id)
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_datetime_to_str(cls, v):
        """Convert datetime to ISO string."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class CreateTodoSchema(Schema):
    title: str
    description: str = ""
    completed: bool = False
    priority: str = "medium"


class UpdateTodoSchema(Schema):
    title: str | None = None
    description: str | None = None
    completed: bool | None = None
    priority: str | None = None
