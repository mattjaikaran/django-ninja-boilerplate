import uuid
from datetime import datetime

from ninja import Schema


class NotificationSchema(Schema):
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


class CreateNotificationSchema(Schema):
    user_id: str
    type: str
    title: str
    body: str
    data: dict = {}
    action_url: str = ""


class NotificationListSchema(Schema):
    unread_count: int
    items: list[NotificationSchema]
