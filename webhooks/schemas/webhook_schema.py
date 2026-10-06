from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, field_validator

from core.schemas.base_schema import CamelCaseSchema

# Webhook.url is a Django URLField (max_length 200) and is POSTed to.
WEBHOOK_URL_PATTERN = r"^https?://\S+$"
# Matches WebhookDelivery.event (max_length 100).
WebhookEvent = Annotated[str, Field(min_length=1, max_length=100)]


class WebhookSchema(CamelCaseSchema):
    id: str
    name: str
    url: str
    secret: str
    events: list[str]
    headers: dict[str, str]
    is_active: bool
    created_at: str
    updated_at: str

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


class CreateWebhookSchema(CamelCaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., max_length=200, pattern=WEBHOOK_URL_PATTERN)
    events: list[WebhookEvent]
    headers: dict[str, str] = Field(default_factory=dict)
    secret: str = Field("", max_length=256)


class UpdateWebhookSchema(CamelCaseSchema):
    name: str | None = Field(None, min_length=1, max_length=100)
    url: str | None = Field(None, max_length=200, pattern=WEBHOOK_URL_PATTERN)
    events: list[WebhookEvent] | None = None
    headers: dict[str, str] | None = None
    secret: str | None = Field(None, max_length=256)
    is_active: bool | None = None


class WebhookDeliverySchema(CamelCaseSchema):
    id: str
    webhook_id: str
    event: str
    payload: dict[str, Any]  # schema-ok: free-form event payload
    response_status: int | None
    response_body: str
    attempt_count: int
    next_retry_at: str | None
    delivered_at: str | None
    error: str
    is_successful: bool
    created_at: str
    updated_at: str

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
