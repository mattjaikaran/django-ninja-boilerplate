# Complete Worked Examples

> These are full vertical-slice examples showing how to build features in this codebase.
> Copy the relevant example when asking an LLM to build a similar feature.

---

## Example 1: Simple CRUD — Notes App

A user-scoped notes resource with title, content, and pinned status.

### 1. Model — `notes/models/note.py`

```python
from django.conf import settings
from django.db import models

from core.models import SoftDeleteModel


class Note(SoftDeleteModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    is_pinned = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.title

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_pinned"]),
        ]
```

### 2. Schemas — `notes/schemas/note_schema.py`

```python
from datetime import datetime

from pydantic import Field, field_validator

from core.schemas.base_schema import CamelCaseSchema


class NoteSchema(CamelCaseSchema):
    id: str
    title: str
    content: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime


class CreateNoteSchema(CamelCaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = ""
    is_pinned: bool = False

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()


class UpdateNoteSchema(CamelCaseSchema):
    title: str | None = Field(None, min_length=1, max_length=255)
    content: str | None = None
    is_pinned: bool | None = None
```

### 3. Service — `notes/services/note_service.py`

```python
import logging

from core.services.base_service import CRUDService

from notes.models import Note

logger = logging.getLogger(__name__)


class NoteService(CRUDService[Note]):
    model = Note

    def get_queryset(self):
        return super().get_queryset().select_related("user")

    def get_user_notes(self, user, **filters):
        qs = self.get_queryset().filter(user=user)
        if search := filters.get("search"):
            qs = qs.filter(title__icontains=search)
        if filters.get("pinned_only"):
            qs = qs.filter(is_pinned=True)
        return qs

    def create_for_user(self, user, data: dict) -> Note:
        return self.create({**data, "user": user}, user=user)

    def toggle_pin(self, user, note_id: str) -> Note:
        from api.exceptions import NotFoundError

        note = self.get_queryset().filter(id=note_id, user=user).first()
        if not note:
            raise NotFoundError(message="Note not found")
        note.is_pinned = not note.is_pinned
        note.save(update_fields=["is_pinned", "updated_at"])
        return note
```

### 4. Controller — `notes/controllers/note_controller.py`

```python
import logging

from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import handle_exceptions, log_api_call
from notes.models import Note
from notes.schemas import CreateNoteSchema, NoteSchema, UpdateNoteSchema
from notes.services import NoteService

logger = logging.getLogger(__name__)


@api_controller("/notes", tags=["Notes"])
class NoteController:

    def __init__(self):
        self.service = NoteService()

    @http_get("/", response={200: list[NoteSchema]})
    @handle_exceptions()
    @log_api_call()
    def list_notes(
        self,
        request,
        search: str | None = None,
        pinned_only: bool = False,
    ):
        notes = self.service.get_user_notes(
            request.user, search=search, pinned_only=pinned_only
        )
        return 200, notes

    @http_get("/{note_id}", response={200: NoteSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_note(self, request, note_id: str):
        note = get_object_or_404(Note, id=note_id, user=request.user)
        return 200, note

    @http_post("/", response={201: NoteSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_note(self, request, payload: CreateNoteSchema):
        note = self.service.create_for_user(request.user, payload.model_dump())
        return 201, note

    @http_put("/{note_id}", response={200: NoteSchema, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_note(self, request, note_id: str, payload: UpdateNoteSchema):
        note = get_object_or_404(Note, id=note_id, user=request.user)
        for attr, value in payload.model_dump(exclude_unset=True).items():
            setattr(note, attr, value)
        note.save()
        return 200, note

    @http_post("/{note_id}/toggle-pin", response={200: NoteSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def toggle_pin(self, request, note_id: str):
        note = self.service.toggle_pin(request.user, note_id)
        return 200, note

    @http_delete("/{note_id}", response={204: None, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_note(self, request, note_id: str):
        note = get_object_or_404(Note, id=note_id, user=request.user)
        note.soft_delete(user=request.user)
        return 204, None
```

### 5. Factory — `notes/tests/factories/note_factory.py`

```python
import factory

from core.tests.factories import UserFactory
from notes.models import Note


class NoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Note

    title = factory.Faker("sentence", nb_words=4)
    content = factory.Faker("text", max_nb_chars=500)
    is_pinned = False
    user = factory.SubFactory(UserFactory)
    created_by = factory.SelfAttribute("user")
    updated_by = factory.SelfAttribute("user")


class PinnedNoteFactory(NoteFactory):
    is_pinned = True
```

### 6. Tests — `notes/tests/test_note.py`

```python
import pytest

from core.tests.factories import UserFactory
from notes.models import Note
from notes.tests.factories import NoteFactory, PinnedNoteFactory


@pytest.mark.django_db
class TestNoteAPI:

    def test_create_note(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(
            "/api/notes/",
            {"title": "My Note", "content": "Hello"},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.json()["title"] == "My Note"
        assert Note.objects.filter(user=user).count() == 1

    def test_list_notes_scoped_to_user(self, authenticated_client):
        client, user = authenticated_client
        NoteFactory.create_batch(3, user=user)
        other = UserFactory()
        NoteFactory.create_batch(2, user=other)

        response = client.get("/api/notes/")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 3

    def test_search_notes(self, authenticated_client):
        client, user = authenticated_client
        NoteFactory(user=user, title="Django Tips")
        NoteFactory(user=user, title="React Hooks")

        response = client.get("/api/notes/?search=django")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert "Django" in items[0]["title"]

    def test_get_note(self, authenticated_client):
        client, user = authenticated_client
        note = NoteFactory(user=user)
        response = client.get(f"/api/notes/{note.id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(note.id)

    def test_cannot_access_other_users_note(self, authenticated_client):
        client, _ = authenticated_client
        other = UserFactory()
        note = NoteFactory(user=other)
        response = client.get(f"/api/notes/{note.id}")
        assert response.status_code == 404

    def test_update_note(self, authenticated_client):
        client, user = authenticated_client
        note = NoteFactory(user=user, title="Old Title")
        response = client.put(
            f"/api/notes/{note.id}",
            {"title": "New Title"},
            content_type="application/json",
        )
        assert response.status_code == 200
        note.refresh_from_db()
        assert note.title == "New Title"

    def test_toggle_pin(self, authenticated_client):
        client, user = authenticated_client
        note = NoteFactory(user=user, is_pinned=False)
        response = client.post(f"/api/notes/{note.id}/toggle-pin")
        assert response.status_code == 200
        note.refresh_from_db()
        assert note.is_pinned is True

    def test_delete_note_soft_deletes(self, authenticated_client):
        client, user = authenticated_client
        note = NoteFactory(user=user)
        response = client.delete(f"/api/notes/{note.id}")
        assert response.status_code == 204
        assert not Note.objects.filter(id=note.id).exists()
        assert Note.all_objects.filter(id=note.id).exists()

    def test_unauthenticated_access_denied(self, api_client):
        response = api_client.get("/api/notes/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestNoteModel:

    def test_str_representation(self):
        note = NoteFactory(title="My Note")
        assert str(note) == "My Note"

    def test_default_ordering(self):
        user = UserFactory()
        regular = NoteFactory(user=user, is_pinned=False)
        pinned = PinnedNoteFactory(user=user)
        notes = list(Note.objects.filter(user=user))
        assert notes[0] == pinned
```

### 7. Admin — `notes/admin/note_admin.py`

```python
from django.contrib import admin
from unfold.admin import ModelAdmin

from notes.models import Note


@admin.register(Note)
class NoteAdmin(ModelAdmin):
    list_display = ["title", "user", "is_pinned", "is_active", "created_at"]
    list_filter = ["is_pinned", "is_active", "created_at"]
    search_fields = ["title", "content", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]
```

### 8. Registration — `api/urls.py`

```python
# 1. Add import at top of file
from notes.controllers import NoteController

# 2. Add to api.register_controllers() call
api.register_controllers(
    # ... existing controllers ...
    NoteController,
)
```

### 9. Module Exports

```python
# notes/models/__init__.py
from .note import Note

__all__ = ["Note"]

# notes/schemas/__init__.py
from .note_schema import CreateNoteSchema, NoteSchema, UpdateNoteSchema

__all__ = ["NoteSchema", "CreateNoteSchema", "UpdateNoteSchema"]

# notes/services/__init__.py
from .note_service import NoteService

__all__ = ["NoteService"]

# notes/controllers/__init__.py
from .note_controller import NoteController

__all__ = ["NoteController"]

# notes/admin/__init__.py
from .note_admin import NoteAdmin

__all__ = ["NoteAdmin"]

# notes/tests/factories/__init__.py
from .note_factory import NoteFactory, PinnedNoteFactory

__all__ = ["NoteFactory", "PinnedNoteFactory"]
```

---

## Example 2: Resource with Relationships — Projects + Tasks

A project that has many tasks, demonstrating nested resources and cross-model queries.

### Model — `projects/models/project.py`

```python
from django.conf import settings
from django.db import models

from core.models import SoftDeleteModel


class Project(SoftDeleteModel):
    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planning")
    deadline = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name

    @property
    def task_count(self) -> int:
        return self.tasks.filter(is_active=True).count()

    @property
    def completed_task_count(self) -> int:
        return self.tasks.filter(is_active=True, is_done=True).count()

    class Meta:
        verbose_name = "Project"
        verbose_name_plural = "Projects"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
        ]
```

### Model — `projects/models/task.py`

```python
from django.conf import settings
from django.db import models

from core.models import SoftDeleteModel


class Task(SoftDeleteModel):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    is_done = models.BooleanField(default=False)
    due_date = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.title

    class Meta:
        verbose_name = "Task"
        verbose_name_plural = "Tasks"
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["project", "is_done"]),
            models.Index(fields=["user", "is_done"]),
        ]
```

### Schema with Nested Objects — `projects/schemas/project_schema.py`

```python
from datetime import datetime

from pydantic import Field, field_validator

from core.schemas.base_schema import CamelCaseSchema


class TaskSchema(CamelCaseSchema):
    id: str
    title: str
    description: str
    priority: str
    is_done: bool
    due_date: datetime | None
    created_at: datetime


class ProjectSchema(CamelCaseSchema):
    id: str
    name: str
    description: str
    status: str
    deadline: datetime | None
    task_count: int
    completed_task_count: int
    created_at: datetime
    updated_at: datetime


class ProjectDetailSchema(ProjectSchema):
    """Project with embedded tasks."""
    tasks: list[TaskSchema] = []


class CreateProjectSchema(CamelCaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    status: str = "planning"
    deadline: datetime | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = {"planning", "active", "paused", "completed"}
        if v not in valid:
            raise ValueError(f"Status must be one of: {', '.join(valid)}")
        return v


class UpdateProjectSchema(CamelCaseSchema):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None
    deadline: datetime | None = None


class CreateTaskSchema(CamelCaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    priority: str = "medium"
    due_date: datetime | None = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        valid = {"low", "medium", "high", "urgent"}
        if v not in valid:
            raise ValueError(f"Priority must be one of: {', '.join(valid)}")
        return v
```

### Service — `projects/services/project_service.py`

```python
import logging

from api.exceptions import NotFoundError, ValidationError
from core.services.base_service import CRUDService
from projects.models import Project, Task

logger = logging.getLogger(__name__)


class ProjectService(CRUDService[Project]):
    model = Project

    def get_queryset(self):
        return super().get_queryset().select_related("user").prefetch_related("tasks")

    def get_user_projects(self, user, **filters):
        qs = self.get_queryset().filter(user=user)
        if status := filters.get("status"):
            qs = qs.filter(status=status)
        if search := filters.get("search"):
            qs = qs.filter(name__icontains=search)
        return qs

    def create_for_user(self, user, data: dict) -> Project:
        return self.create({**data, "user": user}, user=user)

    def add_task(self, user, project_id: str, task_data: dict) -> Task:
        project = self.get_queryset().filter(id=project_id, user=user).first()
        if not project:
            raise NotFoundError(message="Project not found")
        if project.status == "completed":
            raise ValidationError(message="Cannot add tasks to a completed project")
        return Task.objects.create(
            project=project,
            user=user,
            created_by=user,
            **task_data,
        )

    def complete_task(self, user, project_id: str, task_id: str) -> Task:
        task = Task.objects.filter(
            id=task_id, project_id=project_id, user=user
        ).first()
        if not task:
            raise NotFoundError(message="Task not found")
        task.is_done = True
        task.save(update_fields=["is_done", "updated_at"])
        return task
```

### Controller — `projects/controllers/project_controller.py`

```python
import logging

from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import handle_exceptions, log_api_call
from projects.models import Project
from projects.schemas import (
    CreateProjectSchema,
    CreateTaskSchema,
    ProjectDetailSchema,
    ProjectSchema,
    TaskSchema,
    UpdateProjectSchema,
)
from projects.services import ProjectService

logger = logging.getLogger(__name__)


@api_controller("/projects", tags=["Projects"])
class ProjectController:

    def __init__(self):
        self.service = ProjectService()

    @http_get("/", response={200: list[ProjectSchema]})
    @handle_exceptions()
    @log_api_call()
    def list_projects(
        self,
        request,
        status: str | None = None,
        search: str | None = None,
    ):
        return 200, self.service.get_user_projects(
            request.user, status=status, search=search
        )

    @http_get("/{project_id}", response={200: ProjectDetailSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_project(self, request, project_id: str):
        project = get_object_or_404(Project, id=project_id, user=request.user)
        return 200, project

    @http_post("/", response={201: ProjectSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_project(self, request, payload: CreateProjectSchema):
        project = self.service.create_for_user(request.user, payload.model_dump())
        return 201, project

    @http_put("/{project_id}", response={200: ProjectSchema, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_project(self, request, project_id: str, payload: UpdateProjectSchema):
        project = get_object_or_404(Project, id=project_id, user=request.user)
        for attr, value in payload.model_dump(exclude_unset=True).items():
            setattr(project, attr, value)
        project.save()
        return 200, project

    @http_delete("/{project_id}", response={204: None, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_project(self, request, project_id: str):
        project = get_object_or_404(Project, id=project_id, user=request.user)
        project.soft_delete(user=request.user)
        return 204, None

    # --- Nested Task Endpoints ---

    @http_get("/{project_id}/tasks", response={200: list[TaskSchema], 404: dict})
    @handle_exceptions()
    @log_api_call()
    def list_tasks(self, request, project_id: str):
        project = get_object_or_404(Project, id=project_id, user=request.user)
        return 200, project.tasks.filter(is_active=True)

    @http_post("/{project_id}/tasks", response={201: TaskSchema, 400: dict, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_task(self, request, project_id: str, payload: CreateTaskSchema):
        task = self.service.add_task(request.user, project_id, payload.model_dump())
        return 201, task

    @http_post(
        "/{project_id}/tasks/{task_id}/complete",
        response={200: TaskSchema, 404: dict},
    )
    @handle_exceptions()
    @log_api_call()
    def complete_task(self, request, project_id: str, task_id: str):
        task = self.service.complete_task(request.user, project_id, task_id)
        return 200, task
```

---

## Example 3: Celery Background Task — Email Notifications

### Task — `notifications/tasks.py`

```python
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="notifications.send_welcome_email")
def send_welcome_email(user_id: str) -> dict:
    from django.contrib.auth import get_user_model

    from core.services.email.service import EmailService

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        EmailService().send_templated_email(
            template_data={
                "html_template": "emails/welcome.html",
                "context": {"user": user},
            },
            recipient_email=user.email,
        )
        logger.info("Welcome email sent to %s", user.email)
        return {"sent": True, "email": user.email}
    except User.DoesNotExist:
        logger.warning("User %s not found for welcome email", user_id)
        return {"sent": False, "reason": "user_not_found"}


@shared_task(
    name="notifications.send_project_digest",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def send_project_digest(user_id: str) -> dict:
    from django.contrib.auth import get_user_model

    from core.services.email.service import EmailService

    User = get_user_model()
    user = User.objects.get(pk=user_id)
    projects = user.projects.filter(status="active").prefetch_related("tasks")

    summary = []
    for project in projects:
        total = project.tasks.filter(is_active=True).count()
        done = project.tasks.filter(is_active=True, is_done=True).count()
        summary.append({"name": project.name, "total": total, "done": done})

    EmailService().send_templated_email(
        template_data={
            "html_template": "emails/project_digest.html",
            "context": {"user": user, "projects": summary},
        },
        recipient_email=user.email,
    )
    logger.info("Project digest sent to %s (%d projects)", user.email, len(summary))
    return {"sent": True, "projects": len(summary)}
```

### Calling from a Service

```python
# In a service or signal handler
from notifications.tasks import send_welcome_email

def on_user_registered(user):
    send_welcome_email.delay(str(user.id))
```

### Periodic Task Config — `api/celery.py`

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    "daily-project-digest": {
        "task": "notifications.send_project_digest",
        "schedule": crontab(hour=9, minute=0),  # 9 AM daily
    },
}
```

---

## Example 4: Endpoint with Rate Limiting + Pagination

```python
from ninja_extra import api_controller, http_get, http_post
from ninja_extra.pagination import paginate

from api.decorators import handle_exceptions, log_api_call
from api.throttling import rate_limit


@api_controller("/search", tags=["Search"])
class SearchController:

    @paginate
    @http_get("/", response={200: list[SearchResultSchema]})
    @handle_exceptions()
    @log_api_call()
    @rate_limit(requests_per_minute=30)
    def search(self, request, q: str, category: str | None = None):
        qs = SearchIndex.objects.filter(content__icontains=q)
        if category:
            qs = qs.filter(category=category)
        return qs

    @http_post("/reindex", response={200: dict})
    @handle_exceptions()
    @rate_limit(requests_per_minute=1)
    def reindex(self, request):
        from search.tasks import reindex_all
        reindex_all.delay()
        return 200, {"message": "Reindex started"}
```
