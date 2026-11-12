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

Read `todos/` before writing a new resource. It is the reference app, and it
stays in the repository as the reference even when `TODOS_ENABLED=false`
removes it from `INSTALLED_APPS`. Copy these files, in this order:

1. `todos/models/todo.py`
2. `todos/schemas/todo_schema.py`
3. `todos/repositories/todo_repository.py`
4. `todos/services/todo_service.py`
5. `todos/controllers/todo_controller.py` (the other three controllers in that
   folder are teaching variants; never copy them)
6. `todos/tests/test_todo.py` and `todos/tests/factories/todo_factory.py`

## Scaffold a new app

Always start with the generator. It writes the todos shape, wires
`INSTALLED_APPS` and `api/urls.py`, and creates the migration:

```bash
uv run python manage.py generate_feature api_endpoint --app-name <app>
```

`--layers` picks the shape. The default is the todos shape.

| `--layers` | Shape |
|---|---|
| `repository` (default) | controller -> service -> repository |
| `dto` | the same, and the repository returns frozen-dataclass DTOs |
| `service` | controller -> service; the service runs the owner-scoped queries, no repository |

Then add an `<app>/atlas.py` module so the architecture map describes it, and
run `just check-app-shape`. The APP-SHAPE gate fails an app whose folders,
file names or class names differ from the reference layout, whatever its
model.

## Rules

Follow [`references/code-rules.md`](references/code-rules.md) (the rules
`AGENTS.md` section 08 summarizes) and the testing policy in `AGENTS.md`
section 10. The notes below add only what those rules do not cover.

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
methods, base schemas and test fixtures, and
`.agents/skills/django-ninja-dev/scripts/scaffold_controller.sh` to print a
starting point.
