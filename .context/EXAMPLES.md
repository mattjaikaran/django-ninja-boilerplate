# Worked examples

> For rules, read [`AGENTS.md`](../AGENTS.md). This file only shows code; the reference app is `todos/`. Each example shows only what earlier examples do not.

## Example 1: Notes vertical slice

A user-owned resource. Copy this shape for a new owned resource.

### Model: `notes/models/note.py`

```python
from django.conf import settings
from django.db import models

from core.models import SoftDeleteModel


class Note(SoftDeleteModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes"
    )
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-pinned", "-created_at"]

    def __str__(self):
        return self.title
```

### Schemas: `notes/schemas/note_schema.py`

```python
from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from core.schemas.base_schema import CamelCaseSchema


class NoteSchema(CamelCaseSchema):
    id: str
    title: str
    content: str
    pinned: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Serialize the UUID primary key as a string."""
        return str(v) if isinstance(v, UUID) else v


class CreateNoteSchema(CamelCaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = ""
    pinned: bool = False


class UpdateNoteSchema(CamelCaseSchema):
    title: str | None = Field(None, min_length=1, max_length=255)
    content: str | None = None
    pinned: bool | None = None
```

`CamelCaseSchema.model_dump()` returns camelCase keys (`dueDate`); use it for
responses and logs. For data that goes to the model, call
`model_dump_fields()`, which returns field names (`due_date`).

### Service: `notes/services/note_service.py`

```python
from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from core.services.base_service import CRUDService
from notes.models import Note
from notes.schemas import CreateNoteSchema, UpdateNoteSchema


class NoteService(CRUDService[Note]):
    """Owner-scoped CRUD for Note. Another user's note is a 404."""

    model = Note

    def list_for_user(self, user: Any, search: str | None = None) -> QuerySet[Note]:
        queryset = self.get_queryset().filter(user=user)
        if search:
            queryset = queryset.filter(title__icontains=search)
        return queryset

    def get_for_user(self, note_id: UUID, user: Any) -> Note:
        return get_object_or_404(self.get_queryset(), id=note_id, user=user)

    def create_for_user(self, payload: CreateNoteSchema, user: Any) -> Note:
        return self.create({**payload.model_dump_fields(), "user": user}, user=user)

    def update_for_user(
        self, note_id: UUID, payload: UpdateNoteSchema, user: Any
    ) -> Note:
        note = self.get_for_user(note_id, user)
        return self.update(
            note.pk, payload.model_dump_fields(exclude_unset=True), user=user
        )

    def delete_for_user(self, note_id: UUID, user: Any) -> None:
        self.delete(self.get_for_user(note_id, user).pk, user=user)  # soft delete
```

`CRUDService` sets `created_by` and `updated_by`, runs `full_clean()`, and
soft-deletes models that have `is_active`. Its `get_by_id`, `update` and
`delete` are not owner-scoped, so call `get_for_user` first.

### Controller: `notes/controllers/note_controller.py`

```python
from uuid import UUID

from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_extra.pagination import PageNumberPaginationExtra, paginate
from ninja_extra.schemas import PaginatedResponseSchema
from ninja_jwt.authentication import JWTAuth

from api.decorators import log_api_call
from notes.schemas import CreateNoteSchema, NoteSchema, UpdateNoteSchema
from notes.services import NoteService


@api_controller("/notes", tags=["Notes"], auth=JWTAuth())
class NoteController:
    def __init__(self):
        self.service = NoteService()

    @http_get("/", response={200: PaginatedResponseSchema[NoteSchema]})
    @log_api_call()
    @paginate(PageNumberPaginationExtra)
    def list_notes(self, request, search: str | None = None):
        return self.service.list_for_user(request.user, search=search)

    @http_post("/", response={201: NoteSchema, 400: dict})
    @log_api_call(include_payload=True)
    def create_note(self, request, payload: CreateNoteSchema):
        return 201, self.service.create_for_user(payload, request.user)

    @http_get("/{note_id}", response={200: NoteSchema, 404: dict})
    @log_api_call()
    def get_note(self, request, note_id: UUID):
        return 200, self.service.get_for_user(note_id, request.user)

    @http_put("/{note_id}", response={200: NoteSchema, 400: dict, 404: dict})
    @log_api_call(include_payload=True)
    def update_note(self, request, note_id: UUID, payload: UpdateNoteSchema):
        return 200, self.service.update_for_user(note_id, payload, request.user)

    @http_delete("/{note_id}", response={204: None, 404: dict})
    @log_api_call()
    def delete_note(self, request, note_id: UUID):
        self.service.delete_for_user(note_id, request.user)
        return 204, None
```

A paginated handler returns the queryset, not a `(status, data)` tuple. The
body is `{"count", "next", "previous", "results"}`; clients send `?page=` and
`?page_size=`.

### Factory: `notes/tests/factories/note_factory.py`

```python
import factory

from core.tests.factories import UserFactory
from notes.models import Note


class NoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Note

    title = factory.Faker("sentence", nb_words=4)
    content = factory.Faker("text", max_nb_chars=200)
    user = factory.SubFactory(UserFactory)
```

### Tests: `notes/tests/test_note.py`

One file: a create contract test and an ownership test, on the real database.
The `authenticated_client` fixture in `conftest.py` returns `(client, user)`.

```python
import pytest

from core.tests.factories import UserFactory
from notes.models import Note
from notes.tests.factories import NoteFactory


@pytest.mark.django_db
class TestNoteAPI:
    def test_create_returns_camel_case_and_stores_owner(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(
            "/api/notes/", {"title": "Plan", "pinned": True}, content_type="application/json"
        )
        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Plan"
        assert body["pinned"] is True
        assert "createdAt" in body
        note = Note.objects.get(id=body["id"])
        assert note.user == user
        assert note.created_by == user

    def test_other_users_note_is_not_found(self, authenticated_client):
        client, _ = authenticated_client
        note = NoteFactory(user=UserFactory())
        assert client.get(f"/api/notes/{note.id}").status_code == 404
        assert client.delete(f"/api/notes/{note.id}").status_code == 404
        note.refresh_from_db()
        assert note.is_active is True
```

### Registration and exports

Add `"notes"` to `INSTALLED_APPS` in `api/settings/common.py`, run
`makemigrations notes`, and register the controller in `api/urls.py`:

```python
from notes.controllers import NoteController

api.register_controllers(
    # ... existing controllers ...
    NoteController,
)
```

Export every public class with `__all__`. Repeat this shape in
`notes/schemas/`, `notes/services/`, `notes/controllers/` and
`notes/tests/factories/`:

```python
# notes/models/__init__.py
from notes.models.note import Note

__all__ = ["Note"]
```

For an admin page, copy `todos/admin/todo_admin.py` (Unfold `ModelAdmin`).

## Example 2: Relationships

A project owns many tasks. `Project` is an owned model like `Note`, with
`user` and `name`. This example shows only the foreign key, the nested schema
and the service queryset.

### Child model: `projects/models/task.py`

```python
from django.db import models

from core.models import SoftDeleteModel


class Task(SoftDeleteModel):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="tasks"
    )
    title = models.CharField(max_length=255)
    done = models.BooleanField(default=False)
```

### Nested schema: `projects/schemas/project_schema.py`

```python
from uuid import UUID

from pydantic import AliasPath, Field, field_validator

from core.schemas.base_schema import CamelCaseSchema


class TaskSchema(CamelCaseSchema):
    title: str
    done: bool


class ProjectDetailSchema(CamelCaseSchema):
    id: str
    name: str
    owner_email: str = Field(validation_alias=AliasPath("user", "email"))
    tasks: list[TaskSchema] = []

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        return str(v) if isinstance(v, UUID) else v
```

`AliasPath("user", "email")` reads a forward foreign key. For `tasks`, the
Ninja schema getter turns the related manager into a list.

### Service queryset: `projects/services/project_service.py`

```python
from django.db.models import QuerySet

from core.services.base_service import CRUDService
from projects.models import Project


class ProjectService(CRUDService[Project]):
    model = Project

    def get_queryset(self) -> QuerySet[Project]:
        # select_related: forward FK, one JOIN.
        # prefetch_related: reverse FK, one extra query for all rows.
        return super().get_queryset().select_related("user").prefetch_related("tasks")
```

Every method that starts from `self.get_queryset()` gets the same loading,
including a `get_for_user` written as in Example 1.

## Example 3: Background task

`shared_task` from `api.tasks` returns a `TaskHandle` that behaves the same on
every `TASK_BACKEND`. See `docs/TASK_BACKENDS.md`.

### Task: `notes/tasks.py`

```python
import logging

from django.core.mail import send_mail

from api.tasks import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="notes.send_pinned_digest", max_retries=3)
def send_pinned_digest(user_id: str) -> None:
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        logger.error("User %s not found", user_id)
        return

    titles = user.notes.filter(pinned=True).values_list("title", flat=True)
    try:
        send_mail("Your pinned notes", "\n".join(titles), None, [user.email])
    except Exception as exc:
        raise send_pinned_digest.retry(user_id, exc=exc, countdown=60)
```

- Pass IDs as strings, not model instances. Load the row in the task.
- `.retry()` returns a `TaskRetry` signal; `raise` it. After `max_retries`
  retries, the worker raises `TaskMaxRetriesExceeded`.
- With `bind=True`, the task gets a `TaskContext` as its first argument.

Dispatch from a service method:

```python
def queue_digest(self, user: Any) -> None:  # NoteService
    send_pinned_digest.delay(str(user.id))
```

With `TASK_BACKEND=none`, `.delay()` raises `TaskDispatchDisabled`. A direct
call, `send_pinned_digest(user_id)`, runs in the current process.

### Periodic run (Celery backend only)

Add an entry to `app.conf.beat_schedule` in `api/celery.py`, which already
imports `crontab`. The `task` value must match the `name=` of the task.

```python
    "notes-pinned-digest-daily": {
        "task": "notes.send_pinned_digest",
        "schedule": crontab(hour=9, minute=0),
    },
```

## Example 4: Rate limiting and pagination

`NINJA_EXTRA["THROTTLE_CLASSES"]` in `api/settings/common.py` applies
`AnonRateThrottle` and `UserRateThrottle` to every route. Add a scoped
throttle only for an expensive or abusable operation. For pagination, see the
`list_notes` handler in Example 1.

### Per-operation throttle

Add this handler to `NoteController`. It is a static path, so put it before
the first `/{note_id}` handler.

```python
from ninja_extra.throttling import DynamicRateThrottle, throttle

from core.schemas.base_schema import MessageResponse


# Inside NoteController:
    @http_post("/digest", response={202: MessageResponse, 429: dict})
    @log_api_call()
    @throttle(DynamicRateThrottle, scope="notes-digest")
    def send_digest(self, request):
        self.service.queue_digest(request.user)
        return 202, {"message": "Digest queued"}
```

Add the scope to `NINJA_EXTRA["THROTTLE_RATES"]` in `api/settings/common.py`:

```python
"notes-digest": "3/hour",
```

To throttle every route on a controller, pass
`throttle=DynamicRateThrottle(scope="...")` to `@api_controller`, as
`core/controllers/otp_controller.py` does. `handle_throttled` in `api/urls.py`
returns 429 with a `Retry-After` header and a `retry_after` body field.
