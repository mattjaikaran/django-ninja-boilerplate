# System Prompt for LLMs Working with Django Ninja Boilerplate

> Copy this entire file as a system prompt or context file when working with any LLM on this codebase.
> Compatible with: Claude Code, Cursor, GitHub Copilot, ChatGPT, any LLM-powered dev tool.

---

## Identity

You are building a Django REST API using **Django Ninja Extra** with class-based controllers. This is NOT Django REST Framework (DRF). Do NOT use serializers, viewsets, or DRF patterns. This is NOT vanilla Django Ninja — we use `ninja_extra` for class-based controllers, not function-based routers.

## Framework Stack

| Layer | Technology | Import From |
|-------|-----------|-------------|
| API Framework | Django Ninja Extra | `ninja_extra` |
| Routing | Class-based controllers | `ninja_extra.api_controller` |
| HTTP methods | Decorators | `ninja_extra.http_get`, `http_post`, `http_put`, `http_delete` |
| Schemas | Pydantic v2 via Ninja | `ninja.Schema` |
| Auth | JWT | `ninja_jwt` |
| ORM | Django 5.2+ | `django.db.models` |
| Base Models | Custom hierarchy | `core.models.base` |
| Services | Generic CRUD | `core.services.base_service` |
| Exceptions | Custom hierarchy | `api.exceptions` |
| Decorators | Error handling + logging | `api.decorators` |
| Testing | pytest + Factory Boy | `pytest`, `factory` |
| Package Manager | uv | NEVER pip, NEVER poetry |

## The Architecture (Read This First)

Every feature follows a **5-layer vertical slice**:

```
Request → Controller → Service → Model → Database
                ↕            ↕
            Schema      Exception
```

### Layer Responsibilities

| Layer | File Location | Responsibility | Does NOT Do |
|-------|--------------|----------------|-------------|
| **Model** | `app/models/name.py` | Schema definition, relationships, Meta | Business logic, validation |
| **Schema** | `app/schemas/name_schema.py` | Request/response validation, serialization | Database queries |
| **Service** | `app/services/name_service.py` | Business logic, QuerySet building, validation rules | HTTP concerns, status codes |
| **Controller** | `app/controllers/name_controller.py` | HTTP interface, status codes, routing | Business logic, direct ORM queries |
| **Test** | `app/tests/test_name.py` | Behavior verification | Implementation testing |

### Controller is a Thin HTTP Adapter

Controllers do THREE things:
1. Accept the request and parse the payload (via schema)
2. Delegate to a service
3. Return a status code and response

```python
# CORRECT — controller delegates to service
@http_post("/", response={201: ItemSchema})
@handle_exceptions()
def create(self, request, payload: CreateItemSchema):
    item = self.service.create_for_user(request.user, payload.model_dump())
    return 201, item

# WRONG — business logic in controller
@http_post("/", response={201: ItemSchema})
def create(self, request, payload: CreateItemSchema):
    if Item.objects.filter(user=request.user).count() >= 100:  # NO
        raise ValidationError("Too many items")  # NO
    item = Item.objects.create(user=request.user, **payload.model_dump())  # NO
    send_notification.delay(item.id)  # NO
    return 201, item
```

## File Structure for Every New Feature

When asked to create a new feature/resource called `{name}`, create these files:

```
{app}/
├── models/
│   ├── __init__.py          # Add: from .{name} import {Name}
│   └── {name}.py            # Model class
├── schemas/
│   ├── __init__.py          # Add: from .{name}_schema import {Name}Schema, Create{Name}Schema, Update{Name}Schema
│   └── {name}_schema.py     # 3 schemas: Response, Create, Update
├── services/
│   ├── __init__.py          # Add: from .{name}_service import {Name}Service
│   └── {name}_service.py    # Service class extending CRUDService
├── controllers/
│   ├── __init__.py          # Add: from .{name}_controller import {Name}Controller
│   └── {name}_controller.py # Controller with CRUD endpoints
├── tests/
│   ├── factories/
│   │   ├── __init__.py      # Add: from .{name}_factory import {Name}Factory
│   │   └── {name}_factory.py
│   └── test_{name}.py       # Tests
└── admin/
    ├── __init__.py           # Add: from .{name}_admin import {Name}Admin
    └── {name}_admin.py       # Admin config
```

Then register the controller in `api/urls.py`.

## Model Rules

### Inheritance Hierarchy

Choose the right base class:

| Base Class | Use When | Provides |
|-----------|----------|----------|
| `TimestampedModel` | Lightweight, no audit trail needed | UUID pk, created_at, updated_at |
| `AuditBaseModel` | Need created_by/updated_by tracking | Above + created_by, updated_by |
| `SoftDeleteBaseModel` | Need soft delete + audit | Above + is_active, deleted_at, metadata |
| `SoftDeleteModel` | **Default choice** — full features | Above + ActiveManager, all_objects |

### Model Template

```python
from django.conf import settings
from django.db import models

from core.models import SoftDeleteModel


class {Name}(SoftDeleteModel):
    {CHOICES} = [
        ("option_a", "Option A"),
        ("option_b", "Option B"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="{name_plural}",
    )
    # Add fields here

    def __str__(self) -> str:
        return self.{display_field}

    class Meta:
        verbose_name = "{Name}"
        verbose_name_plural = "{Name Plural}"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]
```

### What base models give you for free (DO NOT redeclare):
- `id` — UUID primary key
- `created_at` — auto timestamp
- `updated_at` — auto timestamp
- `created_by` — ForeignKey to User (nullable)
- `updated_by` — ForeignKey to User (nullable)
- `is_active` — Boolean (soft delete flag)
- `deleted_at` — DateTimeField (nullable)
- `metadata` — JSONField (default empty dict)
- `soft_delete()`, `restore()`, `hard_delete()`, `set_metadata()` methods
- `objects` manager (excludes soft-deleted), `all_objects` manager (includes everything)

## Schema Rules

### CRITICAL: Use CamelCaseSchema, NOT raw Schema

All schemas MUST inherit from `CamelCaseSchema` (from `core.schemas.base_schema`), NOT raw `Schema` from ninja. This auto-converts `snake_case` fields to `camelCase` in JSON responses.

```python
from core.schemas.base_schema import CamelCaseSchema
```

If you use raw `Schema`, your API will return `snake_case` keys which breaks frontend conventions.

### Available Base Schemas (from `core.schemas.base_schema`)

| Schema | Use For |
|--------|---------|
| `CamelCaseSchema` | **Default base** — all custom schemas inherit from this |
| `BaseModelSchema` | Response schemas for models (has `id`, `created_at`, `updated_at`, `is_active`) |
| `TimestampSchema` | Schemas that just need `created_at`, `updated_at` |
| `AuditSchema` | Schemas that need `created_by_id`, `updated_by_id` + timestamps |
| `MessageResponse` | Simple `{message, success}` responses |
| `SuccessResponse` | Standard success response |
| `ErrorResponse` | Standard error response |
| `IdResponse` | Response with just an `id` |
| `PaginatedResponse[T]` | Generic paginated list wrapper |
| `BulkActionSchema` | Input for bulk operations (`ids` + `action`) |
| `BulkActionResponse` | Response for bulk operations |
| `BaseFilterSchema` | Base filter with `search`, `is_active`, date range |
| `BaseSortSchema` | Base sort with `sort_by`, `sort_order` |

### Three Schemas Per Resource

```python
from datetime import datetime

from pydantic import Field, field_validator

from core.schemas.base_schema import CamelCaseSchema


class {Name}Schema(CamelCaseSchema):
    """Response schema — all fields, read-only."""
    id: str
    # include all readable fields
    created_at: datetime
    updated_at: datetime


class Create{Name}Schema(CamelCaseSchema):
    """Create schema — required fields + optional with defaults."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()


class Update{Name}Schema(CamelCaseSchema):
    """Update schema — all fields optional for PATCH semantics."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
```

### Schema Rules
- **ALWAYS inherit from `CamelCaseSchema`** — never raw `Schema`
- `CamelCaseSchema` already sets `from_attributes = True` — do NOT redeclare it
- Response schema: `{Name}Schema` — includes `id`, timestamps, all readable fields
- Create schema: `Create{Name}Schema` — required fields have `...`, optional have defaults
- Update schema: `Update{Name}Schema` — ALL fields are `| None` with `None` default
- Use `Field(...)` for validation constraints
- Use `@field_validator` for custom validation logic
- Convert UUIDs to `str` in response schemas
- Input accepts BOTH `camelCase` and `snake_case` (via `populate_by_name=True`)
- Output always serializes as `camelCase`

## Service Rules

### Service Template

```python
import logging

from core.services.base_service import CRUDService

from {app}.models import {Name}

logger = logging.getLogger(__name__)


class {Name}Service(CRUDService[{Name}]):
    """Service for {Name} business logic."""

    model = {Name}

    def get_queryset(self):
        return super().get_queryset().select_related("user")

    def get_user_{name_plural}(self, user, **filters):
        qs = self.get_queryset().filter(user=user)
        if status := filters.get("status"):
            qs = qs.filter(status=status)
        if search := filters.get("search"):
            qs = qs.filter(name__icontains=search)
        return qs

    def create_for_user(self, user, data: dict) -> {Name}:
        return self.create({**data, "user": user}, user=user)

    def update_for_user(self, user, {name}_id, data: dict) -> {Name}:
        {name} = self.get_queryset().filter(id={name}_id, user=user).first()
        if not {name}:
            from api.exceptions import NotFoundError
            raise NotFoundError(message="{Name} not found")
        return self.update({name}, data, user=user)
```

### CRUDService gives you for free:

**From BaseService:**
- `get_queryset()` — base QuerySet (override to add `select_related`)
- `get_active_queryset()` — filters `is_active=True` automatically
- `get_by_id(id)` → `ModelT | None`
- `get_by_id_or_raise(id)` → `ModelT` (raises `NotFoundError`)
- `exists(id)` → `bool`
- `count(**filters)` → `int`

**From CRUDService:**
- `create(data, user=None)` → `ModelT` — creates with audit fields, runs `full_clean()`
- `update(id, data, user=None)` → `ModelT` — **takes ID, not instance**
- `partial_update(id, data, user=None)` → `ModelT` — filters out `None` values first
- `delete(id, user=None, hard_delete=False)` → `bool` — soft delete by default
- `restore(id, user=None)` → `ModelT` — restore soft-deleted (uses `all_objects`)
- `list(filters=None, ordering=None, limit=None, offset=0)` → `QuerySet`
- `bulk_create(data_list, user=None, batch_size=100)` → `list[ModelT]`
- `bulk_update(instances, fields, user=None, batch_size=100)` → `int`
- `bulk_delete(ids, user=None, hard_delete=False)` → `int`

**IMPORTANT**: `update()` and `delete()` take an **ID**, not a model instance. The service looks up the instance internally and raises `NotFoundError` if not found.

## Controller Rules

### Controller Template

```python
import logging

from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from api.decorators import handle_exceptions, log_api_call

from {app}.models import {Name}
from {app}.schemas import {Name}Schema, Create{Name}Schema, Update{Name}Schema
from {app}.services import {Name}Service

logger = logging.getLogger(__name__)


@api_controller("/{name_plural}", tags=["{Name Plural}"])
class {Name}Controller:

    def __init__(self):
        self.service = {Name}Service()

    @http_get("/", response={200: list[{Name}Schema]})
    @handle_exceptions()
    @log_api_call()
    def list_{name_plural}(
        self,
        request,
        status: str | None = None,
        search: str | None = None,
    ):
        return 200, self.service.get_user_{name_plural}(
            request.user, status=status, search=search
        )

    @http_get("/{{name}_id}", response={200: {Name}Schema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_{name}(self, request, {name}_id: str):
        {name} = get_object_or_404({Name}, id={name}_id, user=request.user)
        return 200, {name}

    @http_post("/", response={201: {Name}Schema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_{name}(self, request, payload: Create{Name}Schema):
        {name} = self.service.create_for_user(request.user, payload.model_dump())
        return 201, {name}

    @http_put("/{{name}_id}", response={200: {Name}Schema, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_{name}(self, request, {name}_id: str, payload: Update{Name}Schema):
        {name} = self.service.update_for_user(
            request.user, {name}_id, payload.model_dump(exclude_unset=True)
        )
        return 200, {name}

    @http_delete("/{{name}_id}", response={204: None, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_{name}(self, request, {name}_id: str):
        {name} = get_object_or_404({Name}, id={name}_id, user=request.user)
        {name}.soft_delete(user=request.user)
        return 204, None
```

### Controller Registration

Controllers are NOT auto-registered by import. You must explicitly add them to `api.register_controllers()` in `api/urls.py`:

```python
# api/urls.py

# 1. Add the import at the top
from {app}.controllers import {Name}Controller

# 2. Add to api.register_controllers() call — order determines Swagger docs order
api.register_controllers(
    NinjaJWTDefaultController,
    HealthCheckController,
    # ... existing controllers ...
    {Name}Controller,  # Add your controller here
)
```

The API instance is `NinjaExtraAPI` (not vanilla `NinjaAPI`). Controllers must be passed to `api.register_controllers()` — just importing them does nothing.

## Decorator Stack

Always apply decorators in this order (outermost first):

```python
@http_get("/")           # 1. HTTP method + route (MUST be first)
@handle_exceptions()      # 2. Error handling
@log_api_call()           # 3. Logging (optional)
@rate_limit(requests_per_minute=30)  # 4. Rate limiting (optional)
def my_endpoint(self, request):
    ...
```

## Exception Hierarchy

Use structured exceptions from `api.exceptions`:

| Exception | HTTP Status | When to Use |
|-----------|-------------|-------------|
| `ValidationError` | 400 | Invalid input, business rule violation |
| `AuthenticationError` | 401 | Missing or invalid credentials |
| `APIPermissionError` | 403 | Authenticated but not authorized |
| `NotFoundError` | 404 | Resource doesn't exist |
| `ConflictError` | 409 | Duplicate or state conflict |
| `RateLimitError` | 429 | Too many requests |
| `ExternalServiceError` | 502 | Third-party API failure |

### Exception Usage

```python
from api.exceptions import NotFoundError, ValidationError

# In services (preferred)
raise NotFoundError(
    message="Item not found",
    code="item_not_found",
    details={"id": str(item_id)},
)

# In controllers (only for HTTP-specific checks)
if not request.user.is_authenticated:
    raise AuthenticationError(message="Authentication required")
```

## Test Rules

### Test Template

```python
import pytest

from core.tests.factories import UserFactory

from {app}.models import {Name}
from {app}.tests.factories import {Name}Factory


@pytest.mark.django_db
class Test{Name}API:

    def test_create_{name}(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(
            "/api/{name_plural}/",
            {{"name": "Test {Name}"}},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert {Name}.objects.filter(user=user).exists()

    def test_list_{name_plural}_scoped_to_user(self, authenticated_client):
        client, user = authenticated_client
        {Name}Factory.create_batch(3, user=user)
        other = UserFactory()
        {Name}Factory.create_batch(2, user=other)

        response = client.get("/api/{name_plural}/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3

    def test_get_{name}(self, authenticated_client):
        client, user = authenticated_client
        obj = {Name}Factory(user=user)
        response = client.get(f"/api/{name_plural}/{{obj.id}}")
        assert response.status_code == 200
        assert response.json()["id"] == str(obj.id)

    def test_cannot_access_other_users_{name}(self, authenticated_client):
        client, user = authenticated_client
        other = UserFactory()
        obj = {Name}Factory(user=other)
        response = client.get(f"/api/{name_plural}/{{obj.id}}")
        assert response.status_code == 404

    def test_update_{name}(self, authenticated_client):
        client, user = authenticated_client
        obj = {Name}Factory(user=user)
        response = client.put(
            f"/api/{name_plural}/{{obj.id}}",
            {{"name": "Updated"}},
            content_type="application/json",
        )
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.name == "Updated"

    def test_delete_{name}(self, authenticated_client):
        client, user = authenticated_client
        obj = {Name}Factory(user=user)
        response = client.delete(f"/api/{name_plural}/{{obj.id}}")
        assert response.status_code == 204
        assert not {Name}.objects.filter(id=obj.id).exists()

    def test_unauthenticated_access_denied(self, api_client):
        response = api_client.get("/api/{name_plural}/")
        assert response.status_code == 401
```

### Factory Template

```python
import factory

from core.tests.factories import UserFactory

from {app}.models import {Name}


class {Name}Factory(factory.django.DjangoModelFactory):
    class Meta:
        model = {Name}

    name = factory.Faker("sentence", nb_words=3)
    user = factory.SubFactory(UserFactory)
    created_by = factory.SelfAttribute("user")
    updated_by = factory.SelfAttribute("user")
```

### Available Test Fixtures (from conftest.py)

| Fixture | Returns | Use For |
|---------|---------|---------|
| `api_client` | Django `Client` | Unauthenticated requests |
| `ninja_client` | Ninja `TestClient` | Ninja-specific endpoint testing |
| `api_test_client` | `APITestClient` | Convenience wrapper (auto `/api` prefix) |
| `user` | User instance | Regular user |
| `staff_user` | User (is_staff=True) | Admin-only endpoints |
| `superuser` | User (is_superuser=True) | Superuser endpoints |
| `verified_user` | User (is_verified=True) | Email-verified user |
| `auth_headers` | `dict` | JWT auth headers for manual use |
| `authenticated_client` | `(Client, User)` tuple | **Most common** — authenticated requests |
| `authenticated_ninja_client` | `(TestClient, User)` tuple | Authenticated Ninja client |
| `authenticated_api_client` | `APITestClient` | Pre-authenticated convenience client |
| `todo` | Todo instance | Example model fixture |
| `todo_list` | `list[Todo]` (5 items) | Batch fixture example |
| `mock_email_backend` | `django.core.mail` | Captures emails in `mail.outbox` |
| `temp_media` | `Path` | Temp dir for file upload tests |
| `assert_num_queries` | context manager | Assert exact query count |

### APITestClient (convenience wrapper)

```python
def test_with_api_client(authenticated_api_client):
    # No need to prefix /api — it's automatic
    response = authenticated_api_client.get("/notes/")
    assert response.status_code == 200
```

## Admin Template

```python
from django.contrib import admin
from unfold.admin import ModelAdmin

from {app}.models import {Name}


@admin.register({Name})
class {Name}Admin(ModelAdmin):
    list_display = ["id", "{display_field}", "user", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["{display_field}", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]
    ordering = ["-created_at"]
```

## Import Ordering

Ruff enforces this order. Follow it in every file:

```python
# 1. __future__
from __future__ import annotations

# 2. Standard library
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

# 3. Third-party (Django, Ninja, Pydantic, Celery)
from django.conf import settings
from django.db import models
from ninja import Schema
from ninja_extra import api_controller, http_get

# 4. First-party (project apps — absolute imports)
from api.decorators import handle_exceptions
from core.models import SoftDeleteModel
from core.services.base_service import CRUDService

# 5. Local (relative imports)
from .my_model import MyModel
```

## Naming Conventions

| Entity | Pattern | Example |
|--------|---------|---------|
| App directory | `snake_case` | `user_profiles/` |
| Model file | `{name}.py` | `user_profile.py` |
| Schema file | `{name}_schema.py` | `user_profile_schema.py` |
| Controller file | `{name}_controller.py` | `user_profile_controller.py` |
| Service file | `{name}_service.py` | `user_profile_service.py` |
| Test file | `test_{name}.py` | `test_user_profile.py` |
| Factory file | `{name}_factory.py` | `user_profile_factory.py` |
| Model class | `PascalCase` | `UserProfile` |
| Schema class | `PascalCase` + `Schema` | `UserProfileSchema` |
| Controller class | `PascalCase` + `Controller` | `UserProfileController` |
| Service class | `PascalCase` + `Service` | `UserProfileService` |
| Factory class | `PascalCase` + `Factory` | `UserProfileFactory` |
| URL path | `/plural-noun` | `/user-profiles` |
| URL param | `{singular}_id` | `{user_profile_id}` |

## Commands Reference

```bash
# Package manager — ALWAYS uv, NEVER pip
uv add {package}              # Add dependency
uv run pytest                 # Run tests
uv run python manage.py ...   # Django commands

# Development
make up                       # Start dev server + DB + Redis
make test                     # Run tests
make lint                     # Lint with ruff
make format                   # Format with ruff
make makemigrations           # Create migrations
make migrate                  # Apply migrations
make shell                    # Django shell
make startapp APP=name        # Scaffold new app
```

## Celery Task Template

```python
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="{app}.{task_name}")
def {task_name}({args}) -> dict:
    try:
        # task logic
        logger.info("{task_name} completed: %s", result)
        return {"success": True}
    except Exception as e:
        logger.exception("{task_name} failed: %s", e)
        raise
```

## What You Must NEVER Do

1. **NEVER use DRF patterns** — no serializers, no viewsets, no `rest_framework` imports
2. **NEVER use function-based views** — always `@api_controller` class-based controllers
3. **NEVER put business logic in controllers** — delegate to services
4. **NEVER use pip/npm/yarn** — only `uv` for Python, `bun` for JS
5. **NEVER redeclare fields from base models** — `id`, `created_at`, `updated_at`, etc. are inherited
6. **NEVER mock the database in tests** — use real DB with factories
7. **NEVER import from `rest_framework`** — this is Django Ninja, not DRF
8. **NEVER use `router` from vanilla `django-ninja`** — use `api_controller` from `ninja_extra`
9. **NEVER create loose utility functions for one-time use** — inline them
10. **NEVER skip `@handle_exceptions()` on controller methods**

## Quick Decision Tree

```
Need a new API resource?
  → Create: model → schema → service → controller → factory → tests → admin → register

Need to add a field to an existing model?
  → Edit model → update schemas → makemigrations → migrate → update tests

Need background processing?
  → Create Celery task in {app}/tasks.py → call with .delay()

Need to validate business rules?
  → Add validation in the service layer, raise api.exceptions

Need real-time features?
  → Use Centrifugo (see api/centrifugo.py and deploy/centrifugo/)

Need caching?
  → Use Redis via django-redis (see core/cache/)

Need rate limiting?
  → Add @rate_limit() decorator to controller method
```
