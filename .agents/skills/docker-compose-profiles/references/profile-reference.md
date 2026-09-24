# Profile reference

Service inventory for `docker-compose.yml`.

## dev

| Service | Image / target | Host ports | Notes |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg17` | `${POSTGRES_PORT:-5432}` | Mounts `docker/postgres/init` and `docker/postgres/dumps` |
| `valkey` | `valkey/valkey:8-alpine` | `${VALKEY_PORT:-6379}` | No password in dev |
| `django` | `Dockerfile` target `development` | 8000 | `runserver`, `.:/app` bind mount for hot reload |
| `mcp` | `Dockerfile` target `development` | 8001 | django-ai-boost SSE; needs the `dev` extra |
| `mailhog` | `mailhog/mailhog:v1.0.1` | 1025, 8025 | Catches outgoing mail |

## celery

Celery is opt-in. `docker compose --profile dev --profile celery up -d`
(or `just up-celery`) is the intended command.

| Service | Image / target | Notes |
|---|---|---|
| `db` | `pgvector/pgvector:pg17` | Shared with `dev` |
| `valkey` | `valkey/valkey:8-alpine` | Shared with `dev` |
| `celery-worker` | `Dockerfile` target `production` | `celery -A api worker` |
| `celery-beat` | `Dockerfile` target `production` | Database-backed scheduler |

## prod

| Service | Notes |
|---|---|
| `db-prod` | No host port. Production initdb args with `--data-checksums` |
| `valkey-prod` | `--requirepass ${REDIS_PASSWORD}` |
| `django-prod` | Gunicorn, `expose: 8000` only, static/media/logs volumes |
| `celery-worker-prod` | `-Q default,celery` |
| `celery-beat-prod` | Database-backed scheduler |
| `nginx` | 80. Upstream is `django-prod:8000` (`nginx/nginx.conf`) |

## single

| Service | Notes |
|---|---|
| `db-single` | No host port |
| `redis` | `redis:7.2-alpine` |
| `app` | `deploy/docker/Dockerfile.single`, `${PORT:-8000}` |

## Volumes

`postgres_data`, `valkey_data`, `static_volume`, `media_volume`, `logs_volume`,
`redis_data`. All are `driver: local`.

The prod, single, and dev stacks share `postgres_data`. Switching stacks against
the same volume reuses that database; remove the volume if you need a clean one.

## Adding a service

1. Add it under a `profiles:` key with the profile(s) it belongs to.
2. If it depends on `db`, `valkey`, or a `-prod` base, make sure that base
   service lists your profile.
3. Validate every profile with `docker compose --profile <p> config -q`.
4. Document it in this file and in the profile table in `SKILL.md`.

## Environment

Compose reads `.env`. Do not set `COMPOSE_PROFILES`: deploys run `--profile prod`
in a directory that reuses the same `.env`, and some Compose versions merge the
two profile sets, which would start the dev services in production. The `just`
recipes always pass the profile explicitly.
