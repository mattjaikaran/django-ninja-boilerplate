from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import field_validator


class FileUploadSchema(Schema):
    id: str
    user_id: str
    key: str
    filename: str
    content_type: str
    size: int | None
    is_confirmed: bool
    confirmed_at: datetime | None
    is_public: bool
    metadata: dict
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    s3_url: str | None

    model_config = {"from_attributes": True}

    @field_validator("id", "user_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str:
        if isinstance(v, UUID):
            return str(v)
        return str(v)


class GeneratePresignedUrlSchema(Schema):
    filename: str
    content_type: str
    size: int | None = None
    is_public: bool = False
    folder: str = "uploads"


class PresignedUrlResponseSchema(Schema):
    upload_url: str
    upload_fields: dict
    file_id: str
    key: str
    expires_in: int


class ConfirmUploadSchema(Schema):
    size: int | None = None


class DownloadUrlResponseSchema(Schema):
    download_url: str
    expires_in: int
