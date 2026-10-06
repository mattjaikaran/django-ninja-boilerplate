import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from core.schemas.base_schema import CamelCaseSchema

# Values match notifications.models.Notification.NOTIFICATION_TYPES.
NotificationType = Literal["in_app", "email", "push"]


class NotificationSchema(CamelCaseSchema):
    id: uuid.UUID
    user_id: uuid.UUID
    type: NotificationType
    title: str
    body: str
    data: dict[str, Any]  # schema-ok: free-form notification payload
    action_url: str
    is_read: bool
    read_at: datetime | None
    sent_at: datetime | None
    error: str
    created_at: datetime
    updated_at: datetime


class CreateNotificationSchema(CamelCaseSchema):
    user_id: str
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    data: dict[str, Any] = Field(  # schema-ok: free-form notification payload
        default_factory=dict,
    )
    action_url: str = Field("", max_length=500)


class NotificationListSchema(CamelCaseSchema):
    unread_count: int
    items: list[NotificationSchema]
