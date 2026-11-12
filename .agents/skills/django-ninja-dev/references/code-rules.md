# Code rules

The rules `AGENTS.md` section 08 summarizes. Read this before you write a
model, schema, controller, service or migration. Wrong vs. right code for the
same rules: `.omp/rules/django-ninja-anti-patterns.md`; lookup tables:
`.omp/rules/backend-conventions.md`.

## Django ORM and models

- No database access or `try/except` around ORM lookups in a controller: use
  a service and `get_object_or_404`.
- Migrations are linearized, never merged. **Never run
  `makemigrations --merge`** and never add a merge migration.
- Never edit a migration that is already on `main`; run `makemigrations`, or
  renumber your own files.
- After you add or change a model or a migration, and before you push, run
  `just migrations-check`.
- On a migration conflict (two leaf nodes, or the same number as main) run
  `just migrations-renumber` (dry run), then
  `just migrations-renumber --apply`. It renames only your own files after
  main's latest and migrates a scratch DB.
- When it prints `escalate to owner` (`RunPython`, `RunSQL`, `RemoveField`,
  `RenameField`, `DeleteModel`, `replaces`, or a clashing `AlterField`), stop
  and report it. Rule exceptions live in `api/settings/migration_lint.py`;
  inline `# safe-migrations: ignore` comments are banned. Existing findings
  live in `scripts/baselines/migration-safety.json`.
- Never hide invalid state with a fallback. Fail loud with
  `ImproperlyConfigured` or a 500 that carries the real error.
- No `.raw()` or `.extra()`: use the ORM, `Subquery` or `OuterRef`.
- `select_related`: forward FK and one-to-one. `prefetch_related`: reverse FK
  and many-to-many.
- Default base: `SoftDeleteModel` (`core.models.base`; other bases in
  `rule://backend-conventions`). Never redeclare `id`, `created_at`,
  `updated_at`, `created_by`, `updated_by`, `is_active`, `deleted_at`,
  `deleted_by` or `metadata`.
- Models: `{Name}` in PascalCase, `user` FK with
  `related_name="{name_plural}"`; fields, relationships and `Meta` only.

## Django Ninja

- Django Ninja Extra, not DRF: no `rest_framework`, serializers or viewsets.
  No `ninja.Router` or `views.py`: one `@api_controller` per file in
  `<app>/controllers/<name>_controller.py`. No `api/` directory inside an app;
  root `api/` is project configuration.
- Schemas inherit `CamelCaseSchema` (`core.schemas.base_schema`; never
  `ninja.Schema`, `ModelSchema`, or a redeclared `from_attributes = True`).
  One `<app>/schemas/<name>_schema.py` per domain (no `schemas/request.py` or
  `schemas/response.py`): `{Name}Schema`, `Create{Name}Schema`,
  `Update{Name}Schema` (all optional). UUIDs are `str`. `model_dump()`
  returns camelCase keys for responses and logs; pass ORM writes
  `model_dump_fields()` (snake_case field names).
- Use `Field(...)`, `Literal` or an `Enum` over a hidden `@field_validator`.
  Frontend Zod schemas come from `docs/openapi/openapi.json`: after a schema
  or route change, run `just openapi` and commit the file.
- Controllers validate, call `self.service` (set in `__init__`) and return
  `(status, data)`; business logic lives in services. Services extend
  `CRUDService[Model]` (`core.services.base_service`), set `model`, and
  override `get_queryset()` for related loading.
- An app may add `<app>/repositories/` for ORM access; the service calls it
  and a controller never does. In an engine module (`engines/<engine>/
  <module>/`), the repository returns frozen-dataclass DTOs from `dtos/`,
  and other modules import only its `services` and `dtos`. See
  `docs/ARCHITECTURE.md`, section Engines.
- Scope user data to `request.user`, never `Model.objects.all()`.
- Decorator order: `@http_*`, `@log_api_call()`, `@validate_request()` (if
  used), `@paginate(PageNumberPaginationExtra)` (list endpoints).
- Register controllers with `api.register_controllers(...)` in
  `api/urls.py`, where exception handlers are registered once. Raise
  `api.exceptions` errors or use `get_object_or_404`; there is no
  `handle_exceptions` decorator.
- Each `__init__.py` in `models/`, `schemas/`, `services/`, `controllers/`
  and `factories/` imports its public classes and sets `__all__`.
- Private controllers: `JWTAuth`. Public operations: `auth=None`. Staff-only:
  `IsAdminUser`.
- Review a new anonymous operation, then add its `(method, path)` to
  `PUBLIC_OPERATIONS` in `core/tests/test_route_auth.py`. Never add routes
  just to pass it: it fails on purpose for accidental public operations.
- Put static paths before every `/{id}` handler (including `PUT` and
  `DELETE`): Ninja binds a pattern where it first appears, so an earlier
  `/{id}` shadows a later static GET. CONVENTIONS (`ROUTE_ORDER`) and the
  smoke route sweep catch it; mark a deliberate case `# route-ok: <reason>`.
- Never exempt an endpoint from CSRF for a browser call. Unsafe methods need
  `X-CSRFToken` (`docs/COOKIE_AUTH.md`).

## Tooling, tasks and code

- `uv`, not `pip` or `poetry`. `bun`, not `npm` or `yarn`. `ruff`, not
  `black`, `isort` or `flake8`. `mypy` for types. `rg` or the justfile
  `search` recipe, not `grep -r`.
- Each new dependency needs a `DEPENDENCIES.md` entry.
- One `docker-compose.yml`: add services under a profile. A service that
  depends on `db` or `valkey` adds its profile to that service's `profiles`.
- `scripts/release.py` commits and tags unless `--dry-run`; it pushes only
  with `--push`, rejects unknown flags, and `--help` prints usage.
- Import `shared_task` from `api.tasks`, not Celery. Keep tasks
  backend-neutral: `.delay()`, and raise `.retry()` from the task handle. A
  new task backend is an optional extra plus a Compose profile; its loader
  fails loud without the package.
- No abstraction before a second real use case; no `import *`. Length cap:
  400 lines by default; `[tool.file-length]` in `pyproject.toml` sets the
  exceptions (for example 1200 in `scripts/`, 800 in `cli/`). Split, do not
  raise a cap.
