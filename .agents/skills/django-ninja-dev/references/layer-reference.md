# Layer reference

Facts about the base classes that `AGENTS.md` and `SKILL.md` do not list.
Read `AGENTS.md` for the rules. Each fact below names its source file.

## Exceptions (`api/exceptions.py`)

Every class extends `BaseAPIException(message=None, code=None, details=None)`.
Raise them from services. The handlers in `api/urls.py` map them.

| Class | Status | Default `code` |
|---|---|---|
| `ValidationError` | 400 | `validation_error` |
| `AuthenticationError` | 401 | `authentication_error` |
| `APIPermissionError` | 403 | `permission_error` |
| `NotFoundError` | 404 | `not_found` |
| `ConflictError` | 409 | `conflict_error` |
| `UserError`, `TodoError` | 422 | `user_error`, `todo_error` |
| `RateLimitError` | 429 | `rate_limit_exceeded` |
| `ExternalServiceError` | 502 | `external_service_error` |

`api.exceptions.ValidationError` is not `django.core.exceptions.ValidationError`.
Import the one you mean.

## Error response bodies

| Cause | Status | Body |
|---|---|---|
| `BaseAPIException` subclass | its `status_code` | `{"error": true, "message", "code", "details"}` (`details` only when not empty) |
| Django `ValidationError` (for example from `full_clean()`) | 400 | `{"error": true, "message", "code": "validation_error"}` |
| `@validate_request()` failure | 400 | `{"error": "Validation failed", "errors", "field_errors", "warnings"}` |
| `Http404`, `get_object_or_404` | 404 | `{"detail": "Not Found"}` (Ninja default) |
| Request schema validation | 422 | `{"detail": [...]}` (Ninja default) |
| `Throttled` | 429 | `{"detail", "retry_after"}` and a `Retry-After` header |
| Any other exception | 500 | `{"error": true, "message": "An internal error occurred", "code": "internal_error"}`; the log line carries the request ID |

## Services (`core/services/base_service.py`)

`CRUDService[Model]` extends `BaseService[Model]`. Set `model = Model`.
`self.logger` is set in `__init__`.

| Method | Returns | Notes |
|---|---|---|
| `get_queryset()` | `QuerySet` | `model.objects.all()`. Override for `select_related`. |
| `get_active_queryset()` | `QuerySet` | Adds `is_active=True` when the model has it. |
| `get_by_id(id)` | instance or `None` | |
| `get_by_id_or_raise(id)` | instance | Raises `NotFoundError`. |
| `exists(id)`, `count(**filters)` | `bool`, `int` | |
| `create(data, user=None)` | instance | Sets `created_by`, runs `full_clean()`, saves in a transaction. |
| `update(id, data, user=None)` | instance | Takes an ID. Sets `updated_by`, runs `full_clean()`. |
| `partial_update(id, data, user=None)` | instance | Drops `None` values, then calls `update()`. |
| `delete(id, user=None, hard_delete=False)` | `True` | Calls `soft_delete()` when the model has `is_active`. |
| `restore(id, user=None)` | instance | Looks up through `all_objects`. |
| `list(filters=None, ordering=None, limit=None, offset=0)` | `QuerySet` | |
| `bulk_create(data_list, user=None, batch_size=100)` | `list` | No `full_clean()`, no `save()` signals. |
| `bulk_update(instances, fields, user=None, batch_size=100)` | `int` | Adds `updated_by` when `user` is set. |
| `bulk_delete(ids, user=None, hard_delete=False)` | `int` | Soft path sets `is_active=False` only, not `deleted_at`. |

Know these before you use the base methods:

- The ID lookups do not scope to an owner. `user` is for audit fields only.
  Check ownership first, or override `get_queryset()` with a user filter:

  ```python
  def update_for_user(self, item_id: str, data: dict, user) -> Item:
      if not self.get_queryset().filter(id=item_id, user=user).exists():
          raise NotFoundError(message="Item not found")
      return self.update(item_id, data, user=user)
  ```

- `create()` and `update()` turn every exception, including `IntegrityError`,
  into a 400 `ValidationError`.
- `partial_update()` cannot set a field to `None`. Use `update()` for that.
- `TodoService` does not extend `CRUDService`. It scopes each lookup with
  `.get(id=todo_id, user=user)` and raises `Http404`.

## Models (`core/models/base.py`)

- `Model.delete()` is a hard delete. `SoftDeleteBaseModel` does not override
  it. Call `instance.soft_delete(user=...)` to soft delete, `restore(user=...)`
  to undo, and `hard_delete()` to delete on purpose.
- `SoftDeleteModel.objects` returns active rows only. `all_objects` returns
  every row.
- `AbstractBaseModel` is an alias of `SoftDeleteBaseModel`, not of
  `SoftDeleteModel`. Its default manager includes soft-deleted rows.
- Metadata helpers save the row: `set_metadata(key, value, user=None)`,
  `remove_metadata(key, user=None)`, `update_metadata(updates, user=None)`.
  `get_metadata(key, default=None)` only reads.

## Schemas (`core/schemas/base_schema.py`)

`CamelCaseSchema.model_dump()` always serializes by alias. It ignores
`by_alias=False`, and `.dict()` behaves the same. The keys are camelCase
(`firstName`): use it for responses and logs only. For data that goes to the
ORM, to `setattr` or to a service dict, call `model_dump_fields()`. It takes
the same arguments (except `by_alias`) and returns field names (`first_name`):

```python
Item.objects.create(user=user, **payload.model_dump_fields())
for key, value in payload.model_dump_fields(exclude_unset=True).items():
    setattr(item, key, value)
```

Base schemas in the same module:

| Schema | Fields |
|---|---|
| `MessageResponse` | `message`, `success=True` |
| `SuccessResponse` | `success=True`, `message` |
| `ErrorResponse` | `error=True`, `message`, `code`, `details` |
| `IdResponse` | `id` |
| `TimestampSchema` | `created_at`, `updated_at` |
| `AuditSchema` | timestamps, `created_by_id`, `updated_by_id` |
| `BaseModelSchema` | `id`, `created_at`, `updated_at`, `is_active` |
| `BaseFilterSchema` | `search`, `is_active`, `created_after`, `created_before` |
| `BaseSortSchema` | `sort_by`, `sort_order` (`SortOrder`, default `desc`) |
| `DateRangeSchema` | `start_date`, `end_date` |
| `StatusUpdateSchema` | `status` (`StatusEnum`) |
| `BulkActionSchema`, `BulkActionResponse` | `ids`, `action`; `success`, `processed`, `failed`, `errors` |

## Controllers and decorators (`api/decorators.py`)

- `log_api_call(include_payload=False, include_response=False,
  log_level=logging.INFO)` logs start, finish, duration and errors, then
  re-raises. It masks `SENSITIVE_FIELDS` in the logged payload, but it
  compares them to camelCase keys, so multi-word names such as `new_password`
  are not masked. Do not set `include_payload=True` on a schema with a
  multi-word secret field.
- `validate_request(validators=None)` runs each validator on the payload and
  returns 400 when one fails. A validator receives the payload as a dict with
  field names (`model_dump_fields()`) and returns
  `api.utils.validation.ValidationResult`.
- Rate limits: `@throttle(DynamicRateThrottle, scope="...")` from
  `ninja_extra.throttling`, or `throttle=` on `@api_controller`. Scopes and
  rates are in `README.md`. In `core/controllers/auth_controller.py`,
  `@throttle` sits between `@http_*` and `@log_api_call()`.
- URL paths are plural kebab-case nouns (`/api-keys`). Path parameters are
  `{<resource>_id}` (`/todos/{todo_id}`).
- Other auth options (`APIKeyAuth`, cookies): `docs/API_KEYS.md`,
  `docs/COOKIE_AUTH.md`.

## Tests (`conftest.py`)

| Fixture | Gives |
|---|---|
| `api_client` | Django `Client` |
| `authenticated_client` | `(Client, user)` with a JWT header |
| `ninja_client`, `authenticated_ninja_client` | Ninja `TestClient`, `(TestClient, user)` |
| `api_test_client`, `authenticated_api_client` | `APITestClient`: prefixes `/api`, JSON by default |
| `user`, `staff_user`, `superuser`, `verified_user` | users |
| `auth_headers` | `{"HTTP_AUTHORIZATION": "Bearer ..."}` |
| `todo`, `todo_list` | example rows |
| `mock_email_backend`, `temp_media`, `assert_num_queries`, `freezer` | helpers |

Every test has database access (autouse fixture), and the cache is cleared
around each test, so throttle buckets do not leak. User factories are in
`core.tests.factories`: `UserFactory`, `AdminUserFactory`, `SuperUserFactory`,
`VerifiedUserFactory`, `InactiveUserFactory`, `OneTimePasswordFactory`.

## Logging

Use `logger = logging.getLogger(__name__)` and `%s` arguments, as the base
service and `todos` do. Ruff ignores `G004`, so it does not flag f-strings in
log calls. `T20` blocks `print()`.
