---
description: Interrupts when model imports the removed handle_exceptions decorator or redeclares base model fields
condition:
  - "handle_exceptions"
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

## If decorator order is wrong or you used `handle_exceptions`:

Decorator order MUST be:
```python
@http_get("/")          # 1st: HTTP method (outermost)
@log_api_call()         # 2nd: logging
@validate_request()     # 3rd: optional validation
@paginate(PageNumberPaginationExtra)  # last, list endpoints only
def endpoint(self, request):
    ...
```

`@http_*` decorators MUST be the outermost decorator.

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

## If you used `handle_exceptions`:

`handle_exceptions` does not exist. Remove the import and the decorator.
Exception handlers are registered once on the shared API in `api/urls.py`.
Raise an `api.exceptions` error or use `get_object_or_404`, and the handler
returns the structured error response.
