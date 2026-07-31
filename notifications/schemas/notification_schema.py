import uuid
from datetime import datetime

from core.schemas.base_schema import CamelCaseSchema


class NotificationSchema(CamelCaseSchema):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: str
    data: dict
    action_url: str
    is_read: bool
    read_at: datetime | None
    sent_at: datetime | None
    error: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateNotificationSchema(CamelCaseSchema):
    user_id: str
    type: str
    title: str
    body: str
    data: dict = {}
    action_url: str = ""


class NotificationListSchema(CamelCaseSchema):
    unread_count: int
    items: list[NotificationSchema]
