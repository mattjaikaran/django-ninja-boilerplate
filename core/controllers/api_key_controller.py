"""API Key management endpoints."""

from django.http import HttpRequest
from ninja_extra import api_controller, http_delete, http_get, http_post
from ninja_jwt.authentication import JWTAuth

from api.decorators import handle_exceptions, log_api_call
from core.schemas.api_key_schema import (
    APIKeyCreatedResponse,
    APIKeyResponse,
    CreateAPIKeyRequest,
    RotateAPIKeyResponse,
)
from core.services.api_key_service import APIKeyService


@api_controller("/api-keys", tags=["API Keys"], auth=JWTAuth())
class APIKeyController:
    """Manage API keys for programmatic access."""

    @http_post("/", response={201: APIKeyCreatedResponse})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_key(self, request: HttpRequest, payload: CreateAPIKeyRequest):
        """Create a new API key. The raw key is only returned once."""
        api_key, raw_key = APIKeyService.create_key(
            user=request.user,
            name=payload.name,
            scopes=payload.scopes,
            expires_in_days=payload.expires_in_days,
        )
        return 201, {
            "key": raw_key,
            "id": str(api_key.id),
            "prefix": api_key.prefix,
            "name": api_key.name,
            "scopes": api_key.scopes,
            "expires_at": api_key.expires_at,
            "created_at": api_key.created_at,
        }

    @http_get("/", response={200: list[APIKeyResponse]})
    @handle_exceptions()
    def list_keys(self, request: HttpRequest, include_revoked: bool = False):
        """List all API keys for the current user."""
        keys = APIKeyService.list_keys(request.user, include_revoked=include_revoked)
        return 200, list(keys)

    @http_delete("/{key_id}", response={200: APIKeyResponse})
    @handle_exceptions()
    @log_api_call()
    def revoke_key(self, request: HttpRequest, key_id: str):
        """Revoke an API key."""
        api_key = APIKeyService.revoke_key(request.user, key_id)
        return 200, api_key

    @http_post("/{key_id}/rotate", response={201: RotateAPIKeyResponse})
    @handle_exceptions()
    @log_api_call()
    def rotate_key(self, request: HttpRequest, key_id: str):
        """Rotate an API key: revokes the old key and creates a new one with the same configuration."""
        new_key, raw_key, old_key = APIKeyService.rotate_key(request.user, key_id)
        return 201, {
            "new_key": raw_key,
            "id": str(new_key.id),
            "prefix": new_key.prefix,
            "name": new_key.name,
            "scopes": new_key.scopes,
            "expires_at": new_key.expires_at,
            "created_at": new_key.created_at,
            "revoked_key_id": str(old_key.id),
        }
