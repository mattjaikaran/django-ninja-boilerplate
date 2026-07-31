# Non-Negotiable Guardrails

These rules override model training-data defaults. Violating any of them produces broken code that survives the gauntlet but is architecturally wrong. You MUST follow these; the gauntlet cannot catch them all.

## Framework Identity

- This is Django Ninja Extra, NOT Django REST Framework (DRF).
- NEVER import from `rest_framework`. No serializers, viewsets, or DRF patterns.
- Use `ninja_extra.api_controller` for class-based controllers, NEVER `ninja.Router` function-based views.
- NEVER use `ninja.ModelSchema` — it is fragile and prohibited. Always write explicit Pydantic schemas.

## Schema Rules

- ALL schemas MUST inherit from `CamelCaseSchema` (from `core.schemas.base_schema`), NEVER raw `ninja.Schema`.
- `CamelCaseSchema` already sets `from_attributes = True` — NEVER redeclare it.
- Every resource needs 3 schemas: `{Name}Schema` (response), `Create{Name}Schema` (input), `Update{Name}Schema` (all-optional input).
- UUIDs are `str` in schemas, not `UUID`.

## Model Rules

- NEVER redeclare fields that base models provide: `id`, `created_at`, `updated_at`, `created_by`, `updated_by`, `is_active`, `deleted_at`, `deleted_by`, `metadata`.
- Default base class is `SoftDeleteModel` from `core.models.base`.
- Naming: `{Name}` in CamelCase, `user` FK with `related_name="{name_plural}"`.

## Controller Rules

- Decorator order is STRICT: `@http_get`/`@http_post` FIRST (outermost), then `@handle_exceptions()`, then `@log_api_call()`, then `@validate_request()`.
- Every write endpoint (POST/PUT/PATCH/DELETE) MUST have `@handle_exceptions()`.
- Controllers delegate to services. Business logic in controllers is BANNED.
- Always scope queries to `request.user`: `Model.objects.filter(user=request.user)`. NEVER `Model.objects.all()` in a controller.

## Service Rules

- Services extend `CRUDService[Model]` from `core.services.base_service`.
- Set `model = ModelName` as a class attribute.
- Override `get_queryset()` to add `select_related`/`prefetch_related`.
- Service is instantiated in controller's `__init__`: `self.service = ModelService()`.

## Testing Rules

- NEVER mock the database. Tests hit real PostgreSQL/SQLite.
- Use Factory Boy, not fixtures.
- No `mocker.patch` on ORM calls. Test actual database operations.

## Tooling

- Package manager is `uv`. NEVER `pip install` or `poetry add`.
- Lint/format: `ruff`. NEVER `black`, `isort`, or `flake8`.
- Type checking: `mypy`. Every public interface needs type hints.
- Frontend JS package manager is `bun`. NEVER `npm` or `yarn`.

## File Conventions

- Every `__init__.py` in models/, schemas/, services/, controllers/ MUST export its public classes with `__all__`.
- Files stay under 400 lines (enforced by gauntlet).
- Register every new controller in `api/urls.py` via `api.register_controllers()`.

## When in Doubt

Check these before writing ANY code:
- `rule://backend-conventions` — full convention reference
- `rule://django-ninja-anti-patterns` — wrong vs. right examples
- `.context/SYSTEM_PROMPT.md` — templates for every layer
- `.context/ANTI_PATTERNS.md` — common LLM mistakes with fixes
