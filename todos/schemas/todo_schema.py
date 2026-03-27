"""Todo schemas for API request/response validation.

This module defines Pydantic schemas for todo-related API operations,
covering full read responses, creation payloads, and partial update payloads.

Routes that use these schemas:
    GET  /todos/        — returns list[TodoSchema]
    GET  /todos/{id}    — returns TodoSchema
    POST /todos/        — accepts CreateTodoSchema, returns TodoSchema
    PUT  /todos/{id}    — accepts UpdateTodoSchema, returns TodoSchema
"""

from datetime import datetime
from uuid import UUID

from pydantic import AliasPath, Field, field_validator

from core.schemas.base_schema import CamelCaseSchema


class TodoSchema(CamelCaseSchema):
    """Full read schema for a Todo instance.

    Returned by all GET and write endpoints. UUID and datetime fields are
    coerced to plain strings so the JSON response is always consistent.

    Attributes:
        id: UUID primary key serialised as a string.
        user: UUID of the owning user, serialised as a string.
        title: Short summary of the todo item.
        description: Longer optional body text.
        completed: Whether the todo has been marked done.
        priority: Priority label (e.g. ``low``, ``medium``, ``high``).
        created_at: ISO 8601 creation timestamp.
        updated_at: ISO 8601 last-modification timestamp.
    """

    id: str
    user: str = Field(validation_alias=AliasPath("user", "id"))
    title: str
    description: str
    completed: bool
    priority: str
    created_at: str
    updated_at: str

    @field_validator("id", "user", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string."""
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


class CreateTodoSchema(CamelCaseSchema):
    """Payload schema for creating a new todo.

    All fields except ``title`` are optional and default to sensible values.

    Attributes:
        title: Required short summary of the todo item.
        description: Optional longer body text. Defaults to empty string.
        completed: Initial completion state. Defaults to ``False``.
        priority: Priority label. Defaults to ``"medium"``.
    """

    title: str
    description: str = ""
    completed: bool = False
    priority: str = "medium"


class UpdateTodoSchema(CamelCaseSchema):
    """Payload schema for partially updating an existing todo.

    All fields are optional. Only fields that are explicitly set in the
    request body will be applied to the todo instance.

    Attributes:
        title: New title, or ``None`` to leave unchanged.
        description: New description, or ``None`` to leave unchanged.
        completed: New completion state, or ``None`` to leave unchanged.
        priority: New priority label, or ``None`` to leave unchanged.
    """

    title: str | None = None
    description: str | None = None
    completed: bool | None = None
    priority: str | None = None
