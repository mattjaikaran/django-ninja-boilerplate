# Useful Prompts for Common Tasks

This file contains copy-paste ready prompts for common development tasks in this Django Ninja boilerplate.

---

## Adding a New API Endpoint

### Basic CRUD Endpoint

```
Add a new API endpoint for [RESOURCE_NAME] with the following:

1. Create the model in `[app_name]/models/[resource].py`:
   - Inherit from `SoftDeleteModel` (or `AbstractBaseModel`)
   - Add a ForeignKey to User if user-scoped
   - Add fields: [list your fields]

2. Create schemas in `[app_name]/schemas/[resource]_schema.py`:
   - ResponseSchema with all fields
   - CreateSchema with required fields
   - UpdateSchema with optional fields

3. Create controller in `[app_name]/controllers/[resource]_controller.py`:
   - Use @api_controller decorator
   - Add CRUD endpoints (list, get, create, update, delete)
   - Use @handle_exceptions and @log_api_call decorators
   - Filter by user for list/get operations

4. Register controller in `api/urls.py`

5. Create factory in `[app_name]/tests/factories/[resource]_factory.py`

6. Create tests in `[app_name]/tests/test_[resource].py`

Follow the patterns from `todos/` app.
```

### Example: Add a Notes endpoint

```
Add a Notes API endpoint following the todos pattern:

1. Model (notes/models/note.py):
   - Inherit from SoftDeleteModel
   - Fields: title (CharField), content (TextField), user (ForeignKey)

2. Schemas (notes/schemas/note_schema.py):
   - NoteSchema, CreateNoteSchema, UpdateNoteSchema

3. Controller (notes/controllers/note_controller.py):
   - NoteController at /notes endpoint
   - CRUD operations with user filtering

4. Register in api/urls.py

5. Add NoteFactory and tests

Use these existing files as reference:
- todos/models/todo.py
- todos/schemas/todo_schema.py
- todos/controllers/todo_controller.py
```

---

## Adding a New Model

### Standard Model

```
Create a new model called [MODEL_NAME] in [app_name]/models/[model_name].py:

Requirements:
- Inherit from SoftDeleteModel (or AbstractBaseModel if no soft delete needed)
- Fields: [list your fields with types]
- Include relationship to User if applicable
- Add choices for any enum-like fields
- Add __str__ method
- Set Meta class with verbose_name

Follow the pattern in todos/models/todo.py and core/models/base.py.

After creating, export it in [app_name]/models/__init__.py.
```

### Example: Create a Project model

```
Create a Project model in projects/models/project.py:

```python
from django.conf import settings
from django.db import models
from core.models import SoftDeleteModel

class Project(SoftDeleteModel):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )
    deadline = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Project"
        verbose_name_plural = "Projects"
        ordering = ["-created_at"]
```

Then export in projects/models/__init__.py:
```python
from .project import Project

__all__ = ["Project"]
```
```

---

## Adding Authentication to an Endpoint

### Require Authentication

```
Add authentication requirement to the [ENDPOINT_NAME] endpoint.

The endpoint should:
1. Require a valid JWT token in Authorization header
2. Access the authenticated user via request.user
3. Filter/scope data to the current user
4. Return 401 if not authenticated

Example pattern:
```python
@http_get("/", response={200: list[ItemSchema], 401: dict})
@handle_exceptions()
@log_api_call()
def list_items(self, request):
    if not request.user or not request.user.is_authenticated:
        return 401, {"error": "Not authenticated"}
    return 200, Item.objects.filter(user=request.user)
```

Note: Django Ninja JWT handles authentication automatically when the endpoint
is registered with the API that has JWT controller.
```

### Add Permission Check

```
Add permission checking to [ENDPOINT_NAME]:

1. Check if user has required permission/role
2. Return 403 Forbidden if not authorized

```python
from api.exceptions import APIPermissionError

@http_post("/admin-action", response={200: dict, 403: dict})
@handle_exceptions()
def admin_action(self, request, payload: ActionSchema):
    if not request.user.is_staff:
        raise APIPermissionError("Admin access required")
    # ... perform action
```
```

### Add Rate Limiting

```
Add rate limiting to [ENDPOINT_NAME]:

```python
from api.throttling import rate_limit

@http_post("/sensitive-action")
@rate_limit(rate=10, period=60)  # 10 requests per minute
@handle_exceptions()
def sensitive_action(self, request, payload: ActionSchema):
    ...
```
```

---

## Writing Tests

### Basic API Test

```
Write tests for the [RESOURCE_NAME] API:

1. Test CRUD operations:
   - test_create_[resource]
   - test_list_[resource]s
   - test_get_[resource]
   - test_update_[resource]
   - test_delete_[resource]

2. Test authorization:
   - test_unauthenticated_access_denied
   - test_cannot_access_others_[resource]

3. Test validation:
   - test_create_with_invalid_data
   - test_update_with_invalid_data

Use these fixtures:
- authenticated_client (returns client, user tuple)
- UserFactory for creating users
- [Resource]Factory for creating test data

Follow the pattern in todos/tests/test_todo.py.
```

### Test Template

```python
import pytest
from core.tests.factories import UserFactory
from [app].tests.factories import [Resource]Factory
from [app].models import [Resource]

@pytest.mark.django_db
class Test[Resource]API:
    def test_create_[resource](self, authenticated_client):
        client, user = authenticated_client
        data = {"field": "value"}
        response = client.post(
            "/api/[resources]/",
            data,
            content_type="application/json"
        )
        assert response.status_code == 201
        assert [Resource].objects.filter(user=user).exists()

    def test_list_[resource]s(self, authenticated_client):
        client, user = authenticated_client
        [Resource]Factory.create_batch(3, user=user)

        # Create resource for another user (should not appear)
        other_user = UserFactory()
        [Resource]Factory(user=other_user)

        response = client.get("/api/[resources]/")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 3

    def test_get_[resource](self, authenticated_client):
        client, user = authenticated_client
        resource = [Resource]Factory(user=user)
        response = client.get(f"/api/[resources]/{resource.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(resource.id)

    def test_cannot_access_others_[resource](self, authenticated_client):
        client, user = authenticated_client
        other_user = UserFactory()
        other_resource = [Resource]Factory(user=other_user)

        response = client.get(f"/api/[resources]/{other_resource.id}")
        assert response.status_code == 404
```

---

## Creating Migrations

### Create Migration for New Model

```
Create a migration for the new [MODEL_NAME] model:

1. Ensure model is properly defined in [app]/models/[model].py
2. Export model in [app]/models/__init__.py
3. Run: make makemigrations
4. Review the generated migration file
5. Run: make migrate

If adding to an existing model, describe the changes:
- Adding field: [field_name] ([field_type])
- Removing field: [field_name]
- Changing field: [field_name] from [old] to [new]
```

### Data Migration

```
Create a data migration to [describe what it does]:

```python
# [app]/migrations/XXXX_[description].py
from django.db import migrations

def forwards_func(apps, schema_editor):
    Model = apps.get_model("[app]", "[Model]")
    # Perform data transformation
    for obj in Model.objects.all():
        obj.new_field = transform(obj.old_field)
        obj.save()

def backwards_func(apps, schema_editor):
    # Reverse the transformation
    pass

class Migration(migrations.Migration):
    dependencies = [
        ("[app]", "XXXX_previous_migration"),
    ]

    operations = [
        migrations.RunPython(forwards_func, backwards_func),
    ]
```
```

---

## Adding Celery Tasks

### Basic Task

```
Create a Celery task for [TASK_DESCRIPTION]:

Add to [app]/tasks.py:

```python
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task(name="[app].[task_name]")
def [task_name](arg1: str, arg2: int) -> dict:
    """[Task description].

    Args:
        arg1: Description
        arg2: Description

    Returns:
        dict: Result with status
    """
    try:
        # Task logic here
        logger.info("[Task name] completed for %s", arg1)
        return {"success": True, "result": "..."}
    except Exception as e:
        logger.exception("[Task name] failed: %s", e)
        raise
```

To call the task:
```python
from [app].tasks import [task_name]

# Async execution
[task_name].delay(arg1, arg2)

# With options
[task_name].apply_async(
    args=[arg1, arg2],
    countdown=60,  # Delay 60 seconds
    queue="high_priority"
)
```
```

### Periodic Task

```
Create a periodic Celery task that runs [SCHEDULE]:

Add to [app]/tasks.py:

```python
@shared_task(name="[app].[task_name]")
def [task_name]():
    """[Task description]. Runs [schedule]."""
    # Task logic
    return {"processed": count}
```

Configure in api/celery.py beat_schedule:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    '[task-name]-daily': {
        'task': '[app].tasks.[task_name]',
        'schedule': crontab(hour=0, minute=0),  # Midnight
    },
    '[task-name]-hourly': {
        'task': '[app].tasks.[task_name]',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```
```

### Email Task

```
Create an async email task:

```python
@shared_task(name="[app].send_[type]_email")
def send_[type]_email(user_id: str, data: dict) -> dict:
    """Send [type] email asynchronously."""
    from django.contrib.auth import get_user_model
    from core.services.email.service import EmailService

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        email_service = EmailService()

        email_service.send_templated_email(
            template_data={
                "html_template": "emails/[type].html",
                "context": {
                    "user": user,
                    **data
                }
            },
            recipient_email=user.email
        )

        return {"sent": True, "email": user.email}
    except User.DoesNotExist:
        return {"sent": False, "reason": "User not found"}
```
```

---

## Creating a New Service

```
Create a service class for [MODEL_NAME]:

```python
# [app]/services/[model]_service.py
from core.services.base_service import CRUDService
from [app].models import [Model]

class [Model]Service(CRUDService[[Model]]):
    """Service for [Model] business logic."""

    model = [Model]

    def get_queryset(self):
        """Add default query optimizations."""
        return super().get_queryset().select_related("user")

    def create_for_user(self, user, data: dict) -> [Model]:
        """Create a [model] for a specific user."""
        data["user"] = user
        return self.create(data, user=user)

    def get_user_[model]s(self, user) -> QuerySet:
        """Get all [model]s for a user."""
        return self.get_queryset().filter(user=user)

    def [custom_method](self, ...):
        """[Description]."""
        # Business logic
        pass
```

Usage in controller:
```python
class [Model]Controller:
    def __init__(self):
        self.service = [Model]Service()

    @http_post("/")
    def create(self, request, payload: Create[Model]Schema):
        item = self.service.create_for_user(
            request.user,
            payload.model_dump()
        )
        return 201, item
```
```

---

## Adding Admin Configuration

```
Add admin configuration for [MODEL_NAME]:

```python
# [app]/admin/[model]_admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin
from [app].models import [Model]

@admin.register([Model])
class [Model]Admin(ModelAdmin):
    list_display = ["id", "name", "user", "created_at", "is_active"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "user__email", "user__username"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]

    fieldsets = (
        (None, {
            "fields": ("name", "description", "user")
        }),
        ("Status", {
            "fields": ("is_active",)
        }),
        ("Metadata", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
```

Export in [app]/admin/__init__.py:
```python
from .[model]_admin import [Model]Admin
```
```

---

## Migrate from Gunicorn to Granian (Rust-based WSGI/ASGI Server)

```
Migrate this Django project from Gunicorn to Granian for better performance.
Granian is a Rust-based HTTP server that supports both WSGI and ASGI interfaces
with significantly better throughput and lower latency than Gunicorn.

### Step 1: Update dependencies in pyproject.toml

Replace:
    "gunicorn>=25.3.0",
With:
    "granian>=2.3.0",

Run: uv lock && uv sync

### Step 2: Update Dockerfile (production CMD)

Replace the Gunicorn CMD block:
```dockerfile
CMD ["gunicorn", "api.wsgi:application", \
    "--bind", "0.0.0.0:8000", \
    "--workers", "3", \
    "--threads", "2", \
    "--worker-class", "gthread", \
    "--worker-tmp-dir", "/dev/shm", \
    "--timeout", "120", \
    "--keep-alive", "5", \
    "--max-requests", "1000", \
    "--max-requests-jitter", "50", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--capture-output", \
    "--enable-stdio-inheritance"]
```

With Granian (WSGI mode — drop-in replacement):
```dockerfile
CMD ["granian", "api.wsgi:application", \
    "--interface", "wsgi", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "3", \
    "--threads", "2", \
    "--blocking-threads", "4", \
    "--respawn-failed-workers", \
    "--access-log"]
```

Or Granian (ASGI mode — for async Django + WebSocket support):
```dockerfile
CMD ["granian", "api.asgi:application", \
    "--interface", "asgi", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "3", \
    "--threads", "2", \
    "--blocking-threads", "4", \
    "--respawn-failed-workers", \
    "--access-log"]
```

### Step 3: Update Dockerfile.uv

Same CMD replacement as Step 2.

### Step 4: Update docker-compose.prod.yml

Replace the gunicorn command in the web service:
```yaml
command: >
  granian api.wsgi:application
  --interface wsgi
  --host 0.0.0.0
  --port 8000
  --workers 3
  --threads 2
  --blocking-threads 4
  --respawn-failed-workers
  --access-log
```

### Step 5: Update deploy/docker/Dockerfile.single

Same CMD pattern as Step 2.

### Step 6: Update deploy/k3s/django.yaml

Replace the gunicorn container args:
```yaml
args:
  - granian
  - api.wsgi:application
  - --interface
  - wsgi
  - --host
  - 0.0.0.0
  - --port
  - "8000"
  - --workers
  - "3"
  - --threads
  - "2"
  - --respawn-failed-workers
  - --access-log
```

### Step 7: Update deploy/paas/railway.json

Replace startCommand:
```json
"startCommand": "python manage.py migrate --noinput && granian api.wsgi:application --interface wsgi --host 0.0.0.0 --port $PORT --workers 2 --threads 4 --respawn-failed-workers"
```

### Step 8: Update logging configuration

In core/observability/logging.py, replace the "gunicorn" logger entry:
```python
"granian": {
    "handlers": ["console"],
    "level": "INFO",
    "propagate": False,
},
```

### Step 9: Update Makefile

Find any make targets that reference gunicorn and update them to granian.

### Step 10: If switching to ASGI mode (optional, enables async views + WebSocket)

1. Create api/asgi.py if it doesn't exist:
```python
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")
application = get_asgi_application()
```

2. Celery is unaffected — it connects to Redis directly, not through the HTTP server.
   django-celery-beat runs via the celery beat process, not the web server.
   No changes needed for celery or celery-beat.

3. Middleware is fully compatible. Django middleware works the same under
   both WSGI and ASGI. No changes needed.

4. Update all CMD/command entries to use `api.asgi:application` with
   `--interface asgi` instead of `api.wsgi:application` with `--interface wsgi`.

### Step 11: Test the migration

1. Build and run locally:
   docker compose build && docker compose up
2. Verify health check: curl http://localhost:8000/api/health/
3. Verify API: curl http://localhost:8000/api/
4. Run the test suite: make test
5. Load test to compare performance: make load-test (if available)

### Key differences from Gunicorn:
- No --worker-class flag (Granian handles threading natively in Rust)
- No --worker-tmp-dir (Rust manages worker state differently)
- No --max-requests (Granian's Rust runtime doesn't leak memory like Python workers)
- --blocking-threads controls the thread pool for blocking I/O operations
- --respawn-failed-workers replaces Gunicorn's default worker respawning
```

---

## Quick Reference Commands

```bash
# Development
make setup              # Initial project setup
make up                 # Start Docker services
make down               # Stop Docker services
make logs               # View logs
make shell              # Django shell

# Database
make makemigrations     # Create migrations
make migrate            # Apply migrations
make seed-data          # Seed sample data

# Testing
make test               # Run all tests
make test-coverage      # Run with coverage

# Code Quality
make lint               # Run linter
make format             # Format code

# Celery
make celery-worker      # Start Celery worker
make celery-beat        # Start scheduler
make celery-flower      # Start monitoring

# New features
make startapp APP=name  # Create new app
make generate-feature FEATURE=payments PROVIDER=stripe
```
