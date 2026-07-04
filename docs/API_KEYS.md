# API Key Authentication

Built-in API key auth for machine-to-machine access. Complements JWT auth (which is for user sessions) with long-lived API keys for programmatic access by external services, scripts, and integrations.

## How It Works

- Keys are formatted as `{prefix}.{secret}` (e.g., `a1b2c3d4.nR7x...`)
- The `prefix` (8 hex chars) is used for fast DB lookup
- The `secret` is hashed with SHA-256 and never stored in plaintext
- The raw key is shown **once** at creation time — store it securely

## Endpoints

All endpoints require JWT authentication (you must be logged in to manage your keys).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/api-keys/` | Create a new API key |
| `GET` | `/api/api-keys/` | List your API keys |
| `DELETE` | `/api/api-keys/{key_id}` | Revoke a key |
| `POST` | `/api/api-keys/{key_id}/rotate` | Rotate a key (revoke + create new) |

### Create a Key

```bash
curl -X POST http://localhost:8000/api/api-keys/ \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "CI Pipeline", "scopes": ["read:todos", "write:todos"], "expires_in_days": 90}'
```

Response (the `key` field is only returned once):

```json
{
  "key": "a1b2c3d4.nR7xK9mP...",
  "id": "uuid",
  "prefix": "a1b2c3d4",
  "name": "CI Pipeline",
  "scopes": ["read:todos", "write:todos"],
  "expires_at": "2026-10-02T14:00:00Z",
  "created_at": "2026-07-04T14:00:00Z"
}
```

### Use a Key

Send the key in the `X-API-Key` header:

```bash
curl http://localhost:8000/api/todos/ \
  -H "X-API-Key: a1b2c3d4.nR7xK9mP..."
```

## Adding API Key Auth to Controllers

By default, controllers use JWT auth. To also accept API keys, add `APIKeyAuth` to the auth list:

```python
from core.security.api_key_auth import APIKeyAuth
from ninja_jwt.authentication import JWTAuth

@api_controller("/items", tags=["Items"], auth=[JWTAuth(), APIKeyAuth()])
class ItemController:
    """Accepts either JWT Bearer token or X-API-Key header."""

    @http_get("/")
    def list_items(self, request):
        # request.user is set regardless of auth method
        # request.auth is the APIKey instance (when using API key)
        # or the JWT token (when using JWT)
        ...
```

## Scopes

Keys can have granular scopes. Check them in your controller:

```python
@http_post("/")
def create_item(self, request, payload: CreateItemSchema):
    if hasattr(request.auth, "scopes"):
        if "write:items" not in request.auth.scopes:
            return 403, {"error": "Insufficient scope"}
    ...
```

## Key Rotation

Rotate a key to revoke the old one and create a new one with the same name, scopes, and expiry:

```bash
curl -X POST http://localhost:8000/api/api-keys/{key_id}/rotate \
  -H "Authorization: Bearer <jwt_token>"
```

## Django Admin

API keys are visible in the Django admin panel. You can:
- View all keys (prefix, user, status, last used)
- Revoke keys
- Filter by revocation status

Keys cannot be created through the admin — use the API endpoint to ensure the raw key is securely delivered.

## Configuration

```env
API_KEY_AUTH_ENABLED=True       # Enable/disable API key auth
API_KEY_HEADER=X-API-Key        # Header name
API_KEY_PREFIX=bnp              # Optional: project prefix for keys
```

## Security Notes

- Raw keys are SHA-256 hashed before storage — even database access doesn't reveal the secret
- Keys support expiration dates and can be revoked instantly
- `last_used_at` is tracked for auditing
- Use scopes to limit what each key can do
- Rotate keys regularly, especially after team member departures
