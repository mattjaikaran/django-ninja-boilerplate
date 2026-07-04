# Migration Guide

Step-by-step guide for upgrading existing codebases that forked this boilerplate before v1.6.0.

## Overview of Changes in v1.6.0

1. **Valkey replaces Redis** as the default cache/broker (wire-compatible, no data changes)
2. **orjson** is now the global JSON renderer/parser for all API responses
3. **API Key authentication** added (new model, migration required)
4. **Pluggable task queue backends** (Celery remains default, no changes needed)
5. **ty type checker** added alongside mypy
6. New environment variables with backward-compatible defaults

## Step 1: Update Dependencies

```bash
# Pull the latest pyproject.toml changes, then:
uv sync

# If you use optional backends:
uv sync --extra huey        # for Huey
uv sync --extra django-q    # for django-q2
uv sync --extra django-rq   # for django-rq
```

New core dependencies added:
- `django-valkey>=0.4.1`
- `django-vcache>=0.1.0`

New dev dependency:
- `ty>=0.0.1a1`

## Step 2: Redis to Valkey Migration

Valkey is a wire-compatible fork of Redis under the BSD license. The migration is a rename — no data format changes, no protocol changes.

### 2a. Docker Compose

The `redis` service is renamed to `valkey` in `docker-compose.yml` and `docker-compose.prod.yml`. If you have custom Docker Compose overrides:

```yaml
# Before
redis:
  image: redis:7.2-alpine
  command: redis-server ...

# After
valkey:
  image: valkey/valkey:8-alpine
  command: valkey-server ...
```

### 2b. Docker Volumes

If you need to preserve existing Redis data:

```bash
# Stop services
make down

# Rename the volume (if using named volumes)
docker volume create valkey_data
docker run --rm \
  -v django-ninja-boilerplate_redis_data:/source:ro \
  -v django-ninja-boilerplate_valkey_data:/dest \
  alpine sh -c "cp -a /source/. /dest/"

# Start with new config
make up
```

Or simply flush and start fresh (recommended for dev):

```bash
make down-volumes
make up
```

### 2c. Environment Variables

```env
# New canonical variable
VALKEY_URL=valkey://valkey:6379/0

# REDIS_URL still works as a fallback — no changes needed for existing deploys
REDIS_URL=valkey://valkey:6379/0
```

### 2d. Cache Backend

```env
# Default: django-vcache (Rust-based, fastest)
CACHE_BACKEND=vcache

# Alternative: django-valkey (stable django-redis fork)
CACHE_BACKEND=valkey

# Fallback: keep using django-redis
CACHE_BACKEND=redis
```

### 2e. Railway / PaaS Deployment

Railway now offers a native Valkey template: https://railway.com/deploy/valkey-1

Set `VALKEY_URL` in your Railway environment to the Valkey service's internal URL. The `REDIS_URL` alias also works.

## Step 3: orjson Global Renderer

orjson is now the default JSON renderer/parser for all Django Ninja API responses. This is a performance upgrade (2-10x faster) with no breaking changes for API consumers — the output is standard JSON.

### What changed:
- `api/renderers.py` — new `ORJSONRenderer` class
- `api/parsers.py` — new `ORJSONParser` class
- `api/urls.py` — `NinjaExtraAPI` now uses `renderer=ORJSONRenderer()` and `parser=ORJSONParser()`

### If you have custom JSON serialization:

orjson natively handles `datetime`, `uuid`, `dataclass`, and `numpy` types. If you have custom `DjangoJSONEncoder` subclasses or manual `json.dumps()` calls in API responses, they should still work but are now redundant.

### If you override `NinjaExtraAPI`:

Make sure your custom API instance includes the renderer/parser:

```python
from api.renderers import ORJSONRenderer
from api.parsers import ORJSONParser

api = NinjaExtraAPI(
    renderer=ORJSONRenderer(),
    parser=ORJSONParser(),
    ...
)
```

## Step 4: API Key Authentication

A new `APIKey` model is added. Run migrations:

```bash
make migrate
# or
python manage.py migrate
```

This creates the `core_api_key` table. No existing data is affected.

### New endpoints:
- `POST /api/api-keys/` — create key (JWT auth required)
- `GET /api/api-keys/` — list keys
- `DELETE /api/api-keys/{id}` — revoke key
- `POST /api/api-keys/{id}/rotate` — rotate key

### To use API key auth on your controllers:

```python
from core.security.api_key_auth import APIKeyAuth
from ninja_jwt.authentication import JWTAuth

@api_controller("/my-endpoint", auth=[JWTAuth(), APIKeyAuth()])
class MyController:
    ...
```

See `docs/API_KEYS.md` for full documentation.

## Step 5: Task Backend (Optional)

No changes needed if you're using Celery (the default). The new `TASK_BACKEND` env var defaults to `celery`.

To try an alternative backend, see `docs/TASK_BACKENDS.md`.

## Step 6: ty Type Checker (Optional)

ty is added alongside mypy as an optional Rust-based type checker:

```bash
make ty          # Docker
make local-ty    # Local
```

No changes to existing mypy configuration.

## New Environment Variables Checklist

All new env vars have backward-compatible defaults — existing deploys won't break.

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_BACKEND` | `vcache` | Cache backend: `vcache`, `valkey`, or `redis` |
| `VALKEY_URL` | Falls back to `REDIS_URL` | Valkey/Redis connection URL |
| `TASK_BACKEND` | `celery` | Task queue: `celery`, `huey`, `django_q`, `django_rq` |
| `API_KEY_AUTH_ENABLED` | `True` | Enable API key authentication |
| `API_KEY_HEADER` | `X-API-Key` | Header name for API keys |
| `API_KEY_PREFIX` | `bnp` | Project prefix for generated keys |

## New Makefile Targets

| Target | Description |
|--------|-------------|
| `valkey-cli` | Open Valkey CLI |
| `valkey-flush` | Flush Valkey cache |
| `logs-valkey` | Show Valkey logs |
| `debug-valkey` | Check Valkey connectivity |
| `restart-valkey` | Restart Valkey service |
| `up-huey` | Start with Huey worker |
| `up-django-q` | Start with django-q2 worker |
| `up-django-rq` | Start with django-rq worker |
| `worker-huey` | Start Huey worker locally |
| `worker-q` | Start django-q2 cluster locally |
| `worker-rq` | Start django-rq worker locally |
| `ty` / `local-ty` | Run ty type checker |

## Version Compatibility

- **Redis clients/URLs**: `redis://` URLs still work with Valkey (wire-compatible protocol)
- **REDIS_URL env var**: Still read as a fallback for `VALKEY_URL`
- **Docker volumes**: Named volumes changed from `redis_data` to `valkey_data`
- **Makefile**: `redis-*` targets kept as aliases for `valkey-*` targets
