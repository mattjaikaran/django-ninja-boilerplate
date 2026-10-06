# Task queue backends

The project supports five task backends through one `api.tasks` contract, plus
a `none` mode that runs no worker. Set `TASK_BACKEND` in `.env`, then run
`just dev`. The selected profile starts with Django, Postgres, and Valkey.

## Backend comparison

| Backend | Extra | Worker service | Delayed retry |
|---|---|---|---|
| Celery | Base dependency | `celery-worker` and `celery-beat` | Native Celery retry |
| Huey | `huey` | `huey-worker` | Huey scheduling |
| django-q2 | `django-q` | `django-q-worker` | One-time schedule |
| django-rq | `django-rq` | `django-rq-worker` | RQ `enqueue_in` |
| Dramatiq | `dramatiq` | `dramatiq-worker` | Dramatiq message delay |

Docker images install every extra. For host development, install only the
backend you use:

```bash
uv sync --extra huey
uv sync --extra django-q
uv sync --extra django-rq
uv sync --extra dramatiq
```

The loader raises `ImproperlyConfigured` when the selected backend package is
missing. It never falls back to another backend.

## Run without a worker

Set `TASK_BACKEND=none` when the project must not run a task worker:

```env
TASK_BACKEND=none
```

`just dev` then starts only the `dev` profile. Tasks still register, and a
direct call such as `send_welcome(user_id)` runs in the current process.
`task.delay()` and a retry dispatch raise `TaskDispatchDisabled`, because no
worker would consume the message. The mode never drops a job and never runs
it in the request process instead. Catch `TaskDispatchDisabled` from
`api.tasks` only where the caller has a real alternative. Celery beat does not
run, so periodic jobs such as `core.flush_expired_tokens` do not run either.

## Configure the stack

Run the interactive setup command:

```bash
just setup
```

The in-repo `dnm` CLI asks for a backend and writes `TASK_BACKEND` to `.env`.
If you skip the prompt or use `--auto`, it selects Celery.

You can also set the value directly:

```env
TASK_BACKEND=dramatiq
```

Then start the configured stack:

```bash
just dev
```

`just backend-profile` maps `django_q` to the `django-q` Compose profile and
`django_rq` to `django-rq`. Mailhog and MCP remain separate opt-in profiles.

## Define and dispatch tasks

Import `shared_task` from the facade, not from Celery:

```python
from api.tasks import shared_task


@shared_task(name="accounts.send_welcome", max_retries=3)
def send_welcome(user_id: str) -> None:
    ...


send_welcome.delay(str(user.id))
```

The decorator accepts bare and configured forms:

```python
@shared_task
def cleanup() -> None:
    ...


@shared_task(name="reports.build", bind=True, max_retries=5)
def build_report(context, report_id: str) -> None:
    ...
```

A bound task receives `TaskContext`, not a backend-specific object. Prefer the
task handle for retries so the same code runs on all backends:

```python
@shared_task(max_retries=5)
def deliver(delivery_id: str) -> None:
    try:
        send_delivery(delivery_id)
    except Exception as exc:
        raise deliver.retry(
            delivery_id,
            exc=exc,
            countdown=60,
        )
```

Every decorated task exposes these operations:

- `task(*args, **kwargs)`: run synchronously in the current process.
- `task.delay(*args, **kwargs)`: enqueue an immediate run.
- `task.retry(*args, countdown=N, **kwargs)`: create the retry signal that the
  task raises.

For non-Celery backends, the facade tracks the retry attempt in the serialized
message and enforces `max_retries`. Celery delegates retry counting to its
native task request.

## Core task names

The core jobs live in `core/tasks/jobs.py` and the package re-exports them.
Their stable names remain:

- `core.cleanup_expired_otps`
- `core.cleanup_inactive_users`
- `core.send_otp_email`
- `core.health_check`

This layout avoids the old `core/tasks.py` and `core/tasks/` import collision.

## Backend commands

| Profile | Worker command |
|---|---|
| `celery` | `celery -A api worker` plus database-backed beat |
| `huey` | `python manage.py run_huey` |
| `django-q` | `python manage.py qcluster` |
| `django-rq` | `python manage.py rqworker default high low` |
| `dramatiq` | `dramatiq api.tasks.backends.dramatiq_backend ...` |

Use `docker compose --profile dev --profile <backend> logs` to inspect the
selected worker. Do not run two task profiles against the same queues at once.
