---
description: Reference tables for Django Ninja code here (imports by layer, model base classes, naming, schema fields); rules live in AGENTS.md
globs: ["**/*.py"]
---

# Backend reference

Rules live in `AGENTS.md` section 08. This file holds lookup tables only.

## Imports by layer

| Layer | Technology | Import from |
|---|---|---|
| Routing | Class-based controllers | `ninja_extra.api_controller` |
| HTTP methods | Decorators | `ninja_extra.http_get`, `http_post`, `http_put`, `http_delete` |
| Schemas | Pydantic v2 via `CamelCaseSchema` | `core.schemas.base_schema` |
| Auth | JWT | `ninja_jwt` |
| Base models | `SoftDeleteModel` hierarchy | `core.models.base` |
| Services | Generic CRUD | `core.services.base_service` |
| Exceptions | Custom hierarchy | `api.exceptions` |
| Decorators | Logging, validation | `api.decorators` |
| Tests | pytest + Factory Boy | `pytest`, `factory` |

## Layers

`Request > Controller (HTTP adapter) > Service (business logic, validation,
querysets) > Model (fields, relationships, Meta) > DB`. Schemas validate and
serialize requests and responses.

## Model base classes

| Base class | Use when | Provides |
|---|---|---|
| `TimestampedModel` | Lightweight, no audit | UUID pk, `created_at`, `updated_at` |
| `AuditBaseModel` | User tracking | Above + `created_by`, `updated_by` |
| `SoftDeleteBaseModel` (alias `AbstractBaseModel`) | Soft delete + audit | Above + `is_active`, `deleted_at`, `deleted_by`, `metadata` |
| `SoftDeleteModel` | Default | Above + `objects = ActiveManager()`, `all_objects` |

## Schema fields

- `CamelCaseSchema` aliases fields to camelCase with `populate_by_name=True`.
- Required: `Field(...)`. Optional: `Field(None)` or `| None = None`.

## Naming

| Type | Convention | Example |
|---|---|---|
| Models | PascalCase | `Todo`, `UserProfile` |
| Schemas | PascalCase + Schema | `TodoSchema`, `CreateTodoSchema` |
| Controllers | PascalCase + Controller | `TodoController` |
| Services | PascalCase + Service | `TodoService` |
| Factories | PascalCase + Factory | `TodoFactory` |
| Exceptions | PascalCase + Error | `ValidationError` |
| Files | snake_case | `todo_service.py` |
| Tests | `test_` + snake_case | `test_todo.py` |
