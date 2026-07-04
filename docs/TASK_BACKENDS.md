# Task Queue Backends

This boilerplate supports multiple task queue backends via the `TASK_BACKEND` environment variable. Celery is the default and most full-featured option, but lighter alternatives are available for projects that don't need Celery's complexity.

## Quick Comparison

| Feature | Celery | Huey | django-q2 | django-rq |
|---------|--------|------|-----------|-----------|
| **Complexity** | High | Low | Medium | Low |
| **Broker** | Redis, RabbitMQ, SQS | Redis, SQLite, in-memory | Redis, SQS, MongoDB, ORM | Redis only |
| **Scheduling** | django-celery-beat (DB) | Built-in cron | Built-in | rq-scheduler (separate) |
| **Admin UI** | Flower (separate) | Django admin | Django admin (built-in) | Built-in dashboard |
| **Concurrency** | Prefork, eventlet, gevent | Threading, greenlet | Multiprocessing | Threading |
| **Task chains** | Yes (chord, group, chain) | Pipeline | Chain, group | No |
| **Best for** | Production at scale | Small-medium projects | Django-native monitoring | Simple Redis queues |

## Configuration

### Celery (Default)

No changes needed — Celery is configured out of the box.

```env
TASK_BACKEND=celery
CELERY_BROKER_URL=valkey://valkey:6379/0
CELERY_RESULT_BACKEND=valkey://valkey:6379/0
```

```bash
# Docker
make up-celery

# Local
make celery-worker
make celery-beat
make celery-flower
```

### Huey

Lightweight task queue with automatic synchronous mode in development (`DEBUG=True`).

```bash
# Install
uv add huey

# Configure
TASK_BACKEND=huey
```

```bash
# Docker
make up-huey

# Local
make worker-huey
```

**Settings auto-configured when `TASK_BACKEND=huey`:**

```python
HUEY = {
    "huey_class": "huey.RedisHuey",
    "name": "boilerplate",
    "url": REDIS_URL,
    "immediate": DEBUG,  # sync in dev, async in prod
    "consumer": {"workers": 4, "worker_type": "thread"},
}
```

### django-q2

Multiprocessing task queue with built-in Django admin monitoring.

```bash
# Install
uv add django-q2

# Configure
TASK_BACKEND=django_q
```

```bash
# Docker
make up-django-q

# Local
make worker-q
```

### django-rq

Simplest Redis-backed queue with a built-in web dashboard.

```bash
# Install
uv add django-rq rq

# Configure
TASK_BACKEND=django_rq
```

```bash
# Docker
make up-django-rq

# Local
make worker-rq
```

To enable the built-in dashboard, add to `api/urls.py`:

```python
urlpatterns += [path("django-rq/", include("django_rq.urls"))]
```

## Using the Abstraction Layer

For backend-agnostic tasks, use the `shared_task` decorator from `api.tasks`:

```python
from api.tasks import shared_task

@shared_task
def send_welcome_email(user_id):
    ...
```

This decorator automatically adapts to whichever backend is configured. Each backend provides a `.delay()` method for async dispatch.

## Existing Celery Tasks

All existing tasks in `core/tasks.py`, `webhooks/tasks.py`, and `notifications/tasks.py` use Celery's `@shared_task` directly and continue to work unchanged when `TASK_BACKEND=celery` (the default).

If you switch to a different backend, these tasks will need to be updated to use the abstraction layer or rewritten for the new backend.

## Docker Compose Profiles

Each backend has its own Docker Compose profile:

| Profile | Service | Command |
|---------|---------|---------|
| `celery` | `celery-worker`, `celery-beat` | `make up-celery` |
| `huey` | `huey-worker` | `make up-huey` |
| `django-q` | `django-q-worker` | `make up-django-q` |
| `django-rq` | `django-rq-worker` | `make up-django-rq` |
