"""Pydantic schemas for API key endpoints."""

from datetime import datetime

from core.schemas.base_schema import CamelCaseSchema


class CreateAPIKeyRequest(CamelCaseSchema):
    name: str
    scopes: list[str] = []
    expires_in_days: int | None = None


class APIKeyResponse(CamelCaseSchema):
    id: str
    prefix: str
    name: str
    scopes: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreatedResponse(CamelCaseSchema):
    """Returned only at creation time — includes the raw key."""

    key: str
    id: str
    prefix: str
    name: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime


class RevokeAPIKeyRequest(CamelCaseSchema):
    key_id: str


class RotateAPIKeyResponse(CamelCaseSchema):
    """Returned when rotating — old key revoked, new key issued."""

    new_key: str
    id: str
    prefix: str
    name: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime
    revoked_key_id: str
