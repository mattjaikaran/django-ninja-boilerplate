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

## Rules

Follow `AGENTS.md` section 08 (schemas, controllers, services, models,
exports, auth, route order) and the testing policy in section 10. The notes
below add only what those sections do not cover.

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

`@validate_request()` lives in `api/decorators.py`; put it after
`@log_api_call()`. Raise `Http404` or use `get_object_or_404` for missing
rows; the shared handler maps it to a 404.

Add each new model module to the `[[tool.mypy.overrides]]` `var-annotated`
list in `pyproject.toml`; no model in this repo annotates its fields.
`AbstractBaseModel` is an alias for `SoftDeleteBaseModel`, not
`SoftDeleteModel`.

## Verify

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy .
uv run pytest <app>/
uv run python scripts/check_conventions.py
uv run python scripts/check_architecture.py
```

See `references/controller-patterns.md` for the four controller patterns,
`references/layer-reference.md` for exceptions, error bodies, `CRUDService`
methods, base schemas and test fixtures, and `scripts/scaffold_controller.sh`
to print a starting point.
