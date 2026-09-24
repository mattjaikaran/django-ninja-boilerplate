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

- Starting the stack for a task
- A service is missing after `up`
- Adding or changing a service
- Debugging a `depends on undefined service` error

## Profiles

| Profile | Services | Use for |
|---|---|---|
| `dev` | db, valkey, django, mcp, mailhog | Day-to-day work |
| `test` | db, valkey | Running pytest from the host against Postgres |
| `prod` | db-prod, valkey-prod, django-prod, celery-worker-prod, celery-beat-prod, nginx | Production |
| `single` | db-single, redis, app | Single-container PaaS |
| `celery` | db, valkey, celery-worker, celery-beat | Background jobs |
| `realtime` | valkey, centrifugo | Real-time (dev) |
| `realtime-prod` | db-prod, valkey-prod, centrifugo-prod | Real-time (prod) |
| `monitoring` | valkey, flower, jaeger | Celery dashboard, traces |
| `huey`, `django-q`, `django-rq` | db, valkey, and one worker per backend | Swapping Celery out |
| `observability` | jaeger | Traces only |

Always pass a profile. Every service belongs to at least one, so a bare
`docker compose up` starts nothing.

```bash
just dev                       # docker compose --profile dev up -d
docker compose --profile prod up -d
```

## Why the `-prod` suffix

Docker Compose allows exactly one definition per service name in a file. The dev
`django` (development build target, `runserver`, `.:/app` bind mount) and the
production `django` (production target, gunicorn, image-only volumes) cannot
share the name `django`. The same applies to `db`, `valkey`, `centrifugo`, and
the Celery services. Production variants therefore take a `-prod` suffix.

`volumes` is a list, so it cannot be made profile-conditional — that is why a
single parameterised service cannot serve both.

## `depends_on` crosses profiles

A service starts only if every profile it depends on is also active. When you
add a service that depends on `db` or `valkey`, add your profile to that base
service's `profiles` list too, or Compose fails with:

```
service "x" depends on undefined service "y": invalid compose project
```

## Verify

```bash
docker compose --profile dev config -q
docker compose --profile dev config --services
for p in dev test prod single celery realtime realtime-prod monitoring huey django-q django-rq observability; do
  docker compose --profile "$p" config -q
done
```

`-q` validates without printing. Run it for every profile you touch.

See `references/profile-reference.md` for the full service list and ports.
