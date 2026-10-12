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

# STOP: convention violation

Fix this before you continue.

## You used `handle_exceptions`

It does not exist. Remove the import and the decorator. Exception handlers
are registered once on the shared API in `api/urls.py`: raise an
`api.exceptions` error or use `get_object_or_404`, and the handler returns the
structured error. Decorator order stays `@http_*`, `@log_api_call()`,
`@validate_request()`, `@paginate(PageNumberPaginationExtra)`.

## You redeclared a base model field

`SoftDeleteModel` and its parents already provide `id` (UUID pk),
`created_at`, `updated_at`, `created_by`, `updated_by`, `is_active`,
`deleted_at`, `deleted_by` and `metadata`. Remove the field and declare only
fields unique to your model:

```python
class MyModel(SoftDeleteModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
```
