from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from core.schemas.base_schema import CamelCaseSchema

# A MIME type such as "image/png" or "application/vnd.ms-excel".
CONTENT_TYPE_PATTERN = r"^[A-Za-z0-9_.+-]+/[A-Za-z0-9_.+-]+$"
# One or more safe path segments. The folder becomes the S3 key prefix.
FOLDER_PATTERN = r"^[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*$"


class FileUploadSchema(CamelCaseSchema):
    id: str
    user_id: str
    key: str
    filename: str
    content_type: str
    size: int | None
    is_confirmed: bool
    confirmed_at: datetime | None
    is_public: bool
    metadata: dict[str, Any]  # schema-ok: free-form file metadata
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


class GeneratePresignedUrlSchema(CamelCaseSchema):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., max_length=100, pattern=CONTENT_TYPE_PATTERN)
    size: int | None = Field(None, ge=0)
    is_public: bool = False
    # 100 keeps "<folder>/<user uuid>/<uuid>/<filename>" under the 500-char key.
    folder: str = Field("uploads", max_length=100, pattern=FOLDER_PATTERN)


class PresignedUrlResponseSchema(CamelCaseSchema):
    upload_url: str
    upload_fields: dict[str, str]
    file_id: str
    key: str
    expires_in: int


class ConfirmUploadSchema(CamelCaseSchema):
    size: int | None = Field(None, ge=0)


class DownloadUrlResponseSchema(CamelCaseSchema):
    download_url: str
    expires_in: int
