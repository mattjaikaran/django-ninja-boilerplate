---
description: Interrupts when model generates DRF imports, raw ninja.Schema, ModelSchema, or ninja.Router (the most common AI drift patterns)
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

# STOP: wrong framework pattern

This is Django Ninja Extra, not DRF. Fix this before you continue.

- `rest_framework` (serializers, viewsets, `APIView`, `Response`): use
  `ninja_extra` controllers and `CamelCaseSchema`.
- Raw `ninja.Schema` or `class FooSchema(Schema)`: inherit `CamelCaseSchema`
  from `core.schemas.base_schema`. It already sets `from_attributes = True`
  and camelCase aliases.
- `ModelSchema`: prohibited. Write explicit Pydantic schemas.
- `ninja.Router`: use a class-based controller.

```python
from ninja_extra import api_controller, http_get
from core.schemas.base_schema import CamelCaseSchema

class ItemSchema(CamelCaseSchema):
    id: str
    name: str

@api_controller("/items", tags=["Items"])
class ItemController:
    @http_get("/", response={200: list[ItemSchema]})
    def list_items(self, request): ...
```
