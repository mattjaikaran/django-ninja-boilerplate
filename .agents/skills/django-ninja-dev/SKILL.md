---
name: django-ninja-dev
description: >
  Use when adding or changing API endpoints, controllers, schemas, or services
  in this Django Ninja Extra boilerplate. Covers the controller -> service ->
  model layering, schema file layout, decorator order, and controller
  registration. Use when the user mentions "controller", "endpoint", "schema",
  "service", "ninja", "API route", or "new app".
---

# Django Ninja development

This repo uses **Django Ninja Extra**, not Django REST Framework. Controllers
are class-based; business logic lives in services.

## When to use this skill

- Adding a controller or endpoint
- Creating or changing schemas
- Adding a service
- Registering a new controller
- Scaffolding a new app

## Layout

| Concern | Path |
|---|---|
| Controllers | `<app>/controllers/<name>_controller.py` |
| Schemas | `<app>/schemas/<name>_schema.py` |
| Services | `<app>/services/<name>_service.py` |
| Models | `<app>/models/<name>.py` |
| Admin | `<app>/admin/<name>_admin.py` |
| Tests | `<app>/tests/test_<name>.py` |
| Factories | `<app>/tests/factories/<name>_factory.py` |
| Commands | `<app>/management/commands/<name>.py` |

Do not create `views.py`, and do not create an `api/` directory inside an app.
The root `api/` package is project-level configuration only.

Read `todos/controllers/todo_controller.py`, `todos/services/todo_service.py`,
and `todos/schemas/todo_schema.py` before writing a new resource. They are the
canonical example.

## Scaffold a new app

```bash
uv run python manage.py startapp_extended <app>
```

Then:

1. Add `<app>` to `INSTALLED_APPS` in `api/settings/common.py`.
2. Register the controller in `api/urls.py` with `api.register_controllers(...)`.
3. Add an `<app>/atlas.py` module so the architecture map describes it.
4. Run `uv run python manage.py makemigrations <app>`.

## Schemas

- Inherit from `CamelCaseSchema` (`core.schemas.base_schema`). Never use
  `ninja.Schema` or `ModelSchema`.
- `CamelCaseSchema` already sets `from_attributes = True`. Do not redeclare it.
- Write three schemas per resource in one file: `{Name}Schema`,
  `Create{Name}Schema`, `Update{Name}Schema`.
- Use `str` for UUID fields, not `UUID`.

## Controllers

```python
@api_controller("/items", tags=["Items"], auth=JWTAuth())
class ItemController:
    def __init__(self):
        self.service = ItemService()

    @http_post("/", response={201: ItemSchema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    def create_item(self, request, payload: CreateItemSchema):
        return 201, self.service.create(payload, request.user)
```

The `@http_*` decorator is outermost. Register exception handlers on the
shared API instance in `api/urls.py`, not on each operation. This repository
does not define `@handle_exceptions()` or `@validate_request()`.

Controllers are HTTP adapters. They validate, call a service, and return. Put
business logic in the service.

## Services

Services hold business logic and own the queryset. Scope every query to the
user: `Model.objects.filter(user=user)`. Never call `Model.objects.all()` in a
controller that returns user data.

Raise `Http404` (or use `get_object_or_404`) for missing rows. The shared API
exception handler maps it to a 404.

## Models

Extend `core.models.SoftDeleteModel` (or `AbstractBaseModel`, its alias). Never
redeclare `id`, `created_at`, `updated_at`, `created_by`, `updated_by`,
`is_active`, `deleted_at`, `deleted_by`, or `metadata`.

Add the model module to the `[[tool.mypy.overrides]]` `var-annotated` list in
`pyproject.toml`; no model in this repo annotates its fields.

## Package exports

Every `models/`, `schemas/`, `services/`, `controllers/`, and `factories/`
`__init__.py` must import its public classes and set `__all__`. The convention
checker fails the build otherwise.

## Verify

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest <app>/
uv run python scripts/check_conventions.py
uv run python scripts/check_architecture.py
```

See `references/controller-patterns.md` for the four controller patterns, and
`scripts/scaffold_controller.sh` to print a starting point.
