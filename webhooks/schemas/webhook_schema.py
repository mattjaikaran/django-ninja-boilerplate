from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import field_validator


class WebhookSchema(Schema):
    id: str
    name: str
    url: str
    secret: str
    events: list[str]
    headers: dict
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_datetime_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class CreateWebhookSchema(Schema):
    name: str
    url: str
    events: list[str]
    headers: dict = {}
    secret: str = ""


class UpdateWebhookSchema(Schema):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    headers: dict | None = None
    secret: str | None = None
    is_active: bool | None = None


class WebhookDeliverySchema(Schema):
    id: str
    webhook_id: str
    event: str
    payload: dict
    response_status: int | None
    response_body: str
    attempt_count: int
    next_retry_at: str | None
    delivered_at: str | None
    error: str
    is_successful: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

    @field_validator("id", "webhook_id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_datetime_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    @field_validator("next_retry_at", "delivered_at", mode="before")
    @classmethod
    def convert_optional_datetime_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
