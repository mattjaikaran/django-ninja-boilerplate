---
name: docker-compose-profiles
description: >
  Use when starting, changing, or debugging the Docker stack: which Compose
  profile to run, why a service did not start, or how to add a service. Use
  when the user mentions "docker", "compose", "profile", "container", "service",
  "postgres", "valkey", "redis", "centrifugo", "nginx", or "up -d".
---

# Docker Compose profiles

One file: `docker-compose.yml`. There is no separate prod or single file.

## When to use this skill

- Start the stack for a task.
- Diagnose a missing or failed service.
- Add or change a service.
- Change the selected task backend.

## Profiles

| Profile | Services | Use for |
|---|---|---|
| `dev` | db, valkey, django | Day-to-day application stack |
| `test` | db, valkey | Run pytest from the host against Postgres |
| `prod` | db-prod, valkey-prod, django-prod, celery-worker-prod, celery-beat-prod, nginx | Production |
| `single` | db-single, redis, app | Single-container PaaS |
| `celery` | db, valkey, celery-worker, celery-beat | Default task backend |
| `huey` | db, valkey, huey-worker | Huey task backend |
| `django-q` | db, valkey, django-q-worker | django-q2 task backend |
| `django-rq` | db, valkey, django-rq-worker | django-rq task backend |
| `dramatiq` | db, valkey, dramatiq-worker | Dramatiq task backend |
| `realtime` | valkey, centrifugo | Real-time development service |
| `realtime-prod` | db-prod, valkey-prod, centrifugo-prod | Real-time production service |
| `monitoring` | valkey, flower, jaeger | Celery dashboard and traces |
| `mail` | mailhog | Development email capture |
| `mcp` | db, valkey, mcp | Development MCP service |
| `observability` | jaeger | Traces only |
| `decisions-clm` | clm-encoder, clm-api | Optional NVIDIA GPU Qwen3-8B + CLM decision service |
| `decisions-clm-host` | clm-api | CLM API against an encoder outside Compose (`CLM_ENCODER_URL`, e.g. llama.cpp on Apple Silicon) |
| `embeddings` | embedder | Qwen3-Embedding-0.6B for `POST /api/decisions/similar` |

Always pass a profile. Every service belongs to at least one, so a bare
`docker compose up` starts nothing.

```bash
just dev
docker compose --profile prod up -d
```

`just dev` reads `TASK_BACKEND` and `SYSTEMONE_PROVIDER` from `.env`. It starts
one task backend and adds `decisions-clm` only when CLM is selected. Celery and
Laya are the defaults. Start CLM only on a Linux NVIDIA host; Laya needs no GPU.
Mailhog and MCP stay opt-in through `just up-mail` and `just up-mcp`.

## Why the `-prod` suffix

Docker Compose allows exactly one definition per service name in a file. The dev
`django` and production `django-prod` services need different images, commands,
and volumes. Production variants therefore use a `-prod` suffix.

## `depends_on` crosses profiles

A service starts only if every profile it depends on is active. When you add a
service that depends on `db` or `valkey`, add its profile to that base service's
`profiles` list. Task workers also depend on healthy `django` so migrations
finish before workers consume jobs.

## Verify

```bash
docker compose --profile dev config -q
docker compose --profile dev config --services
for p in dev test prod single celery huey django-q django-rq dramatiq realtime realtime-prod monitoring observability mail mcp; do
  docker compose --profile "$p" config -q
done
```

`-q` validates without printing. Run it for every profile you touch.

See `references/profile-reference.md` for the full service list and ports.
