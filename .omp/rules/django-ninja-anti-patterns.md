---
description: Common anti-patterns LLMs produce — DRF imports, wrong schemas, business logic in controllers, missing decorators, unscoped queries
globs: ["**/*.py"]
alwaysApply: true
---

# Anti-Patterns — What NOT to Do

Each anti-pattern shows WRONG code followed by CORRECT code. These are the most common mistakes AI assistants make in this codebase.

## 1. DRF imports — BANNED

WRONG:
```python
from rest_framework import serializers, viewsets, status
from rest_framework.response import Response

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = "__all__"
```

CORRECT:
```python
from ninja_extra import api_controller, http_get, http_post
from core.schemas.base_schema import CamelCaseSchema

class ItemSchema(CamelCaseSchema):
    id: str
    name: str

@api_controller("/items", tags=["Items"])
class ItemController:
    @http_get("/", response={200: list[ItemSchema]})
    def list_items(self, request):
        return 200, Item.objects.filter(user=request.user)
```

## 2. Router function-based views — BANNED

WRONG:
```python
from ninja import Router
router = Router()

@router.get("/items")
def list_items(request):
    return Item.objects.all()
```

CORRECT:
```python
from ninja_extra import api_controller, http_get

@api_controller("/items", tags=["Items"])
class ItemController:
    @http_get("/", response={200: list[ItemSchema]})
    def list_items(self, request):
        return 200, Item.objects.filter(user=request.user)
```

## 3. Raw `Schema` instead of `CamelCaseSchema` — BANNED

WRONG:
```python
from ninja import Schema

class ItemSchema(Schema):
    id: str
    name: str
    class Config:
        from_attributes = True
```

CORRECT:
```python
from core.schemas.base_schema import CamelCaseSchema

class ItemSchema(CamelCaseSchema):
    id: str
    name: str
```

## 4. `ModelSchema` — PROHIBITED

WRONG:
```python
from ninja import ModelSchema

class ItemSchema(ModelSchema):
    class Meta:
        model = Item
        fields = "__all__"
```

CORRECT: Always write explicit Pydantic schemas inheriting from CamelCaseSchema.

## 5. Redeclaring base model fields — BANNED

WRONG:
```python
class Note(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid4)   # ALREADY IN BASE
    created_at = models.DateTimeField(auto_now_add=True)      # ALREADY IN BASE
    updated_at = models.DateTimeField(auto_now=True)          # ALREADY IN BASE
    is_active = models.BooleanField(default=True)             # ALREADY IN BASE
    metadata = models.JSONField(default=dict)                 # ALREADY IN BASE
    name = models.CharField(max_length=255)
```

CORRECT:
```python
class Note(SoftDeleteModel):
    name = models.CharField(max_length=255)
    content = models.TextField(blank=True)
```

## 6. Business logic in controllers — BANNED

WRONG:
```python
@api_controller("/orders", tags=["Orders"])
class OrderController:
    @http_post("/", response={201: OrderSchema})
    def create_order(self, request, payload: CreateOrderSchema):
        # ALL OF THIS BELONGS IN A SERVICE
        if Order.objects.filter(user=request.user, status="pending").count() >= 5:
            raise ValidationError("Too many pending orders")
        order = Order.objects.create(user=request.user, **payload.model_dump())
        for item in payload.items:
            product = Product.objects.get(id=item.product_id)
            if product.stock < item.quantity:
                order.delete()
                raise ValidationError(f"{product.name} out of stock")
            product.stock -= item.quantity
            product.save()
            OrderItem.objects.create(order=order, product=product, quantity=item.quantity)
        send_order_confirmation.delay(str(order.id))
        return 201, order
```

CORRECT — Controller delegates to service:
```python
@api_controller("/orders", tags=["Orders"])
class OrderController:
    def __init__(self):
        self.service = OrderService()

    @http_post("/", response={201: OrderSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_order(self, request, payload: CreateOrderSchema):
        order = self.service.create_order(request.user, payload.model_dump())
        return 201, order
```

## 7. Missing `@handle_exceptions()` — ERROR

WRONG:
```python
@http_get("/{item_id}", response={200: ItemSchema})
def get_item(self, request, item_id: str):
    return 200, get_object_or_404(Item, id=item_id)
```

CORRECT:
```python
@http_get("/{item_id}", response={200: ItemSchema, 404: dict})
@handle_exceptions()
@log_api_call()
def get_item(self, request, item_id: str):
    item = get_object_or_404(Item, id=item_id, user=request.user)
    return 200, item
```

## 8. Wrong decorator order

WRONG:
```python
@handle_exceptions()       # WRONG: must be after @http_get
@http_get("/")
def list_items(self, request):
    ...
```

CORRECT — HTTP method decorator is always first (outermost):
```python
@http_get("/")             # 1st: HTTP method
@handle_exceptions()       # 2nd: error handling
@log_api_call()            # 3rd: logging
def list_items(self, request):
    ...
```

## 9. Unscoped queries — SECURITY BUG

WRONG:
```python
return 200, Note.objects.all()  # Returns EVERYONE'S notes
```

CORRECT:
```python
return 200, Note.objects.filter(user=request.user)
```

## 10. Missing `__init__.py` exports

WRONG — Empty `__init__.py`:
```python
# notes/models/__init__.py is empty
# ImportError: cannot import name 'Note' from 'notes.models'
```

CORRECT:
```python
# notes/models/__init__.py
from .note import Note
__all__ = ["Note"]
```

## 11. Mocking the database in tests — BANNED

WRONG:
```python
def test_create_item(mocker):
    mock_create = mocker.patch("items.models.Item.objects.create")
    mock_create.return_value = Item(id="fake-id")
```

CORRECT — Hit real database:
```python
def test_create_item(authenticated_client):
    client, user = authenticated_client
    response = client.post("/api/items/", {"name": "Test"}, content_type="application/json")
    assert response.status_code == 201
    assert Item.objects.filter(user=user, name="Test").exists()
```

## 12. pip/npm/yarn — BANNED

WRONG: `pip install django-ninja`, `npm install react`, `yarn add typescript`
CORRECT: `uv add django-ninja`, `bun add react`, `bun add typescript`
