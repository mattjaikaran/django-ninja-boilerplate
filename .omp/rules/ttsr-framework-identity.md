---
description: Interrupts when model generates DRF imports, raw ninja.Schema, ModelSchema, or ninja.Router — the most common AI drift patterns
condition:
  - "from rest_framework"
  - "import rest_framework"
  - "from ninja import Schema"
  - "from ninja import.*Schema"
  - "from ninja import ModelSchema"
  - "from ninja import Router"
  - "ninja.Router"
astCondition:
  - "from rest_framework import $$$"
  - "import rest_framework"
  - "class $$$(Schema)"
interruptMode: always
scope:
  - "tool:edit(**/*.py)"
  - "tool:write(**/*.py)"
---

# STOP — Wrong Framework Pattern Detected

You just wrote code that uses a prohibited pattern in this codebase. Fix before continuing.

## If you imported from `rest_framework`:

This is Django Ninja Extra, NOT Django REST Framework. Use:

```python
from ninja_extra import api_controller, http_get, http_post
from core.schemas.base_schema import CamelCaseSchema
```

Never use: `serializers`, `viewsets`, `APIView`, `Response`, or any DRF module.

## If you imported raw `ninja.Schema`:

ALL schemas MUST inherit from `CamelCaseSchema` (from `core.schemas.base_schema`):

```python
# WRONG — just wrote this:
from ninja import Schema
class FooSchema(Schema):
    ...

# CORRECT:
from core.schemas.base_schema import CamelCaseSchema
class FooSchema(CamelCaseSchema):
    ...
```

`CamelCaseSchema` already sets `from_attributes = True` and handles camelCase serialization.

## If you used `ModelSchema`:

`ModelSchema` is fragile and PROHIBITED. Always write explicit Pydantic schemas.

## If you used `ninja.Router`:

Use `@api_controller` class-based controllers from `ninja_extra`, not function-based routers:

```python
# WRONG:
from ninja import Router
router = Router()
@router.get("/items")
def list_items(request): ...

# CORRECT:
from ninja_extra import api_controller, http_get
@api_controller("/items", tags=["Items"])
class ItemController:
    @http_get("/", response={200: list[ItemSchema]})
    def list_items(self, request): ...
```

## If you wrote a class inheriting raw `Schema`:

Replace `class FooSchema(Schema)` with `class FooSchema(CamelCaseSchema)`.
Import CamelCaseSchema from `core.schemas.base_schema`.
