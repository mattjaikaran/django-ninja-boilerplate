# Profile reference

Service inventory for `docker-compose.yml`.

## dev

| Service | Image / target | Host ports | Notes |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg17` | `${POSTGRES_PORT:-5433}` | Mounts the Postgres init and dump directories |
| `valkey` | `valkey/valkey:8-alpine` | `${VALKEY_PORT:-6380}` | No password in development |
| `django` | `Dockerfile` target `development` | `${DJANGO_PORT:-8000}` | `runserver` with a source bind mount |

## Task backends

Run `just dev`. It activates `dev` and the profile selected by `TASK_BACKEND`.

| Profile | Service | Command |
|---|---|---|
| `celery` | `celery-worker`, `celery-beat` | Celery worker and database-backed beat |
| `huey` | `huey-worker` | `python manage.py run_huey` |
| `django-q` | `django-q-worker` | `python manage.py qcluster` |
| `django-rq` | `django-rq-worker` | `python manage.py rqworker default high low` |
| `dramatiq` | `dramatiq-worker` | `dramatiq api.tasks.dramatiq_worker` |

Each worker uses the production image target and depends on healthy `django`,
`db`, and `valkey` services. The images install all five backend extras.

## Opt-in development services

| Profile | Service | Host ports | Notes |
|---|---|---|---|
| `mcp` | `mcp` | 8001 | django-ai-boost SSE; needs the `dev` extra |
| `mail` | `mailhog` | 1025, 8025 | Catches outgoing email |
| `realtime` | `centrifugo` | 8800 | Centrifugo development server |
| `monitoring` | `flower`, `jaeger` | 5555, 16686 | Worker dashboard and traces |
| `decisions-clm` | `clm-encoder`, `clm-api` | 8700 on loopback | NVIDIA GPU Qwen3-8B encoder and CLM head; persistent model caches |
| `decisions-clm-host` | `clm-api` | 8700 on loopback | CLM head against `CLM_ENCODER_URL`; `just clm-encoder-local` serves Qwen3-8B with llama.cpp on the host |
| `embeddings` | `embedder` | internal 8080 | Qwen3-Embedding-0.6B (llama.cpp, CPU) for fixture similarity search |

## prod

| Service | Notes |
|---|---|
| `db-prod` | No host port. Uses `--data-checksums` |
| `valkey-prod` | Requires `${REDIS_PASSWORD}` |
| `django-prod` | Gunicorn, `expose: 8000`, static/media/logs volumes |
| `celery-worker-prod` | Consumes `default,celery` queues |
| `celery-beat-prod` | Database-backed scheduler |
| `nginx` | Port 80 with upstream `django-prod:8000` |

## single

| Service | Notes |
|---|---|
| `db-single` | No host port |
| `redis` | `redis:7.2-alpine` |
| `app` | `deploy/docker/Dockerfile.single`, `${PORT:-8000}` |

## Volumes

`postgres_data`, `valkey_data`, `static_volume`, `media_volume`, `logs_volume`,
`redis_data`, `clm_hf_cache`, and `clm_head_cache` use the local driver.

The prod, single, and dev stacks share `postgres_data`. Remove the volume when
you need an isolated database.

## Add a service

1. Add the service under a `profiles:` key.
2. Add its profile to each `db`, `valkey`, or production base dependency.
3. Validate every affected profile with `docker compose --profile <p> config -q`.
4. Document the service in this file and in `SKILL.md`.

## Environment

Compose reads `.env`. Do not set `COMPOSE_PROFILES`. Deployments can reuse the
same `.env`, and some Compose versions merge that value with command profiles.
The `just` recipes pass profiles explicitly.
