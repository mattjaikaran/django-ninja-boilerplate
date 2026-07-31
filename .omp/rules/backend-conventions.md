---
description: Django Ninja backend conventions — framework identity, decorator order, layer architecture, schemas, models, services, testing
globs: ["**/*.py"]
alwaysApply: true
---

# Django Ninja Backend Conventions

## Framework Identity

| Layer | Technology | Import From |
|-------|-----------|-------------|
| API Framework | Django Ninja Extra | `ninja_extra` |
| Routing | Class-based controllers | `ninja_extra.api_controller` |
| HTTP methods | Decorators | `ninja_extra.http_get`, `http_post`, `http_put`, `http_delete` |
| Schemas | Pydantic v2 via CamelCaseSchema | `core.schemas.base_schema` |
| Auth | JWT | `ninja_jwt` |
| Base Models | SoftDeleteModel hierarchy | `core.models.base` |
| Services | Generic CRUD | `core.services.base_service` |
| Exceptions | Custom hierarchy | `api.exceptions` |
| Decorators | Error handling + logging | `api.decorators` |
| Testing | pytest + Factory Boy | `pytest`, `factory` |
| Package Manager | uv | NEVER pip, NEVER poetry |

## Prohibited Patterns

- `from rest_framework import ...` — NOT DRF
- `from ninja import Router` — use `@api_controller` class-based
- `from ninja import ModelSchema` — use explicit schemas
- `class FooSchema(Schema)` — must be `CamelCaseSchema`
- Redeclaring `id`, `created_at`, `updated_at`, `is_active`, `metadata` in models
- Business logic in controllers — goes in services
- `Model.objects.all()` in controllers — must scope to user
- `pip install`, `poetry add` — use `uv add`
- `npm install`, `yarn add` — use `bun add`
- `mocker.patch` on ORM — test real database
- `black`, `isort`, `flake8` — use `ruff`

## Decorator Order (STRICT)

```
@http_get("/")          # 1st: HTTP method (outermost)
@handle_exceptions()    # 2nd: error handling
@log_api_call()         # 3rd: logging
@validate_request()     # 4th: validation (innermost)
def endpoint(self, request):
    ...
```

## Layer Architecture

```
Request → Controller (thin HTTP adapter) → Service (business logic) → Model (ORM) → DB
```

- Controller: accepts request, delegates to service, returns (status_code, data)
- Service: business logic, validation rules, QuerySet building
- Model: schema definition, relationships, Meta — nothing else
- Schema: request/response validation and serialization

## Model Base Classes

| Base Class | Use When | Provides |
|-----------|----------|----------|
| `TimestampedModel` | Lightweight, no audit | UUID pk, created_at, updated_at |
| `AuditBaseModel` | Need user tracking | Above + created_by, updated_by |
| `SoftDeleteBaseModel` | Soft delete + audit | Above + is_active, deleted_at, metadata |
| `SoftDeleteModel` | Default choice | Above + ActiveManager, all_objects |

DO NOT redeclare: `id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `is_active`, `deleted_at`, `deleted_by`, `metadata`.

## Schema Rules

- ALWAYS inherit from `CamelCaseSchema` (aliases to camelCase, populate_by_name=True)
- `from_attributes = True` is already set by CamelCaseSchema — never redeclare
- 3 schemas per resource: `{Name}Schema` (response), `Create{Name}Schema`, `Update{Name}Schema`
- UUIDs → `str` in schemas
- Required fields: `Field(...)`, optional: `Field(None)` or `| None = None`
- Use `@field_validator` for custom validation

## Naming

| Type | Convention | Example |
|------|-----------|---------|
| Models | PascalCase | `Todo`, `UserProfile` |
| Schemas | PascalCase + Schema | `TodoSchema`, `CreateTodoSchema` |
| Controllers | PascalCase + Controller | `TodoController` |
| Services | PascalCase + Service | `TodoService` |
| Factories | PascalCase + Factory | `TodoFactory` |
| Exceptions | PascalCase + Error | `ValidationError` |
| Files | snake_case | `todo_service.py` |
| Tests | test_ + snake_case | `test_todo.py` |

## File Exports

Every `__init__.py` MUST export public classes:

```python
# models/__init__.py
from .todo import Todo
__all__ = ["Todo"]
```

## Controller Registration

Every new controller MUST be registered in `api/urls.py`:
```python
api.register_controllers(TodoController)
```
