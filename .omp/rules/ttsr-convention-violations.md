---
description: Interrupts when model generates wrong decorator order, missing @handle_exceptions, or redeclares base model fields
condition:
  - "@handle_exceptions.*\n.*@http_"
  - "created_at = models\\.(DateTimeField|DateField)"
  - "updated_at = models\\.(DateTimeField|DateField)"
  - "is_active = models\\.BooleanField"
  - "metadata = models\\.JSONField"
  - "deleted_at = models\\.DateTimeField"
  - "id = models\\.UUIDField"
  - "deleted_by = models\\.ForeignKey"
astCondition:
  - "class $$$($$$): { $$$ is_active = $_ $$$ }"
  - "class $$$($$$): { $$$ id = $_ $$$ }"
  - "class $$$($$$): { $$$ created_at = $_ $$$ }"
  - "class $$$($$$): { $$$ metadata = $_ $$$ }"
interruptMode: always
scope:
  - "tool:edit(**/*.py)"
  - "tool:write(**/*.py)"
---

# STOP — Convention Violation Detected

You just generated code that violates project conventions. Fix before continuing.

## If decorator order is wrong:

Decorator order MUST be:
```python
@http_get("/")          # 1st: HTTP method (outermost)
@handle_exceptions()    # 2nd: error handling
@log_api_call()         # 3rd: logging
@validate_request()     # 4th: validation (innermost)
def endpoint(self, request):
    ...
```

`@http_*` decorators MUST be the outermost decorator. `@handle_exceptions` goes INSIDE them.

## If you redeclared a base model field:

You wrote a field that the base model (`SoftDeleteModel`, `TimestampedModel`, etc.) ALREADY provides. NEVER redeclare these:

- `id` — UUID primary key
- `created_at`, `updated_at` — auto timestamps
- `created_by`, `updated_by` — ForeignKey to User
- `is_active` — Boolean (soft delete flag)
- `deleted_at`, `deleted_by` — soft delete tracking
- `metadata` — JSONField

Remove the redeclared field. Only declare fields unique to your model:

```python
class MyModel(SoftDeleteModel):
    # Only YOUR fields here:
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    # id, created_at, updated_at, is_active, metadata, etc. come from SoftDeleteModel
```

## If you forgot @handle_exceptions on a write endpoint:

Every POST, PUT, PATCH, DELETE endpoint MUST have `@handle_exceptions()`:

```python
@http_post("/", response={201: TodoSchema, 400: dict})
@handle_exceptions()
@log_api_call(include_payload=True)
def create_todo(self, request, payload: CreateTodoSchema):
    ...
```

Without it, exceptions return raw 500 errors instead of structured error responses.
