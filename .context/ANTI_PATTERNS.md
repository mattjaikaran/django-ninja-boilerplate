# Anti-Patterns — What LLMs Get Wrong

> Common mistakes AI coding assistants make when working with this codebase.
> Feed this to your LLM alongside SYSTEM_PROMPT.md to prevent these errors.

---

## 1. Using DRF Instead of Django Ninja

**WRONG** — LLMs default to DRF because it dominates training data:
```python
# WRONG: DRF patterns
from rest_framework import serializers, viewsets, status
from rest_framework.response import Response

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = "__all__"

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
```

**CORRECT** — Django Ninja Extra with class-based controllers:
```python
from ninja import Schema
from ninja_extra import api_controller, http_get, http_post

class ItemSchema(Schema):
    id: str
    name: str
    class Config:
        from_attributes = True

@api_controller("/items", tags=["Items"])
class ItemController:
    @http_get("/", response={200: list[ItemSchema]})
    def list_items(self, request):
        return 200, Item.objects.filter(user=request.user)
```

---

## 2. Using Function-Based Views Instead of Controllers

**WRONG** — Vanilla Django Ninja function-based approach:
```python
from ninja import Router

router = Router()

@router.get("/items")
def list_items(request):
    return Item.objects.all()
```

**CORRECT** — Class-based controller with `@api_controller`:
```python
from ninja_extra import api_controller, http_get

@api_controller("/items", tags=["Items"])
class ItemController:
    @http_get("/", response={200: list[ItemSchema]})
    def list_items(self, request):
        return 200, Item.objects.filter(user=request.user)
```

---

## 3. Redeclaring Base Model Fields

**WRONG** — Redeclaring fields that `SoftDeleteModel` already provides:
```python
class Note(SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid4)  # ALREADY IN BASE
    created_at = models.DateTimeField(auto_now_add=True)      # ALREADY IN BASE
    updated_at = models.DateTimeField(auto_now=True)           # ALREADY IN BASE
    is_active = models.BooleanField(default=True)              # ALREADY IN BASE
    metadata = models.JSONField(default=dict)                  # ALREADY IN BASE
    name = models.CharField(max_length=255)
```

**CORRECT** — Only declare YOUR fields:
```python
class Note(SoftDeleteModel):
    name = models.CharField(max_length=255)
    content = models.TextField(blank=True)
```

---

## 4. Business Logic in Controllers

**WRONG** — Controller doing too much:
```python
@api_controller("/orders", tags=["Orders"])
class OrderController:
    @http_post("/", response={201: OrderSchema})
    def create_order(self, request, payload: CreateOrderSchema):
        # WRONG: All of this belongs in a service
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

**CORRECT** — Controller delegates to service:
```python
@api_controller("/orders", tags=["Orders"])
class OrderController:
    def __init__(self):
        self.service = OrderService()

    @http_post("/", response={201: OrderSchema})
    @handle_exceptions()
    def create_order(self, request, payload: CreateOrderSchema):
        order = self.service.create_order(request.user, payload.model_dump())
        return 201, order
```

---

## 5. Using pip/npm/yarn

**WRONG**:
```bash
pip install django-ninja
npm install react
yarn add typescript
```

**CORRECT**:
```bash
uv add django-ninja
bun add react
bun add typescript
```

---

## 6. Mocking the Database in Tests

**WRONG** — Mocking ORM calls:
```python
@pytest.mark.django_db
def test_create_item(mocker):
    mock_create = mocker.patch("items.models.Item.objects.create")
    mock_create.return_value = Item(id="fake-id", name="Test")
    # This tests nothing real
```

**CORRECT** — Hit the real database:
```python
@pytest.mark.django_db
def test_create_item(authenticated_client):
    client, user = authenticated_client
    response = client.post(
        "/api/items/",
        {"name": "Test"},
        content_type="application/json",
    )
    assert response.status_code == 201
    assert Item.objects.filter(user=user, name="Test").exists()
```

---

## 7. Missing `@handle_exceptions()` Decorator

**WRONG** — Unhandled exceptions return raw 500:
```python
@http_get("/{item_id}", response={200: ItemSchema})
def get_item(self, request, item_id: str):
    return 200, get_object_or_404(Item, id=item_id)
```

**CORRECT** — Always wrap with error handling:
```python
@http_get("/{item_id}", response={200: ItemSchema, 404: dict})
@handle_exceptions()
@log_api_call()
def get_item(self, request, item_id: str):
    return 200, get_object_or_404(Item, id=item_id, user=request.user)
```

---

## 8. Wrong Decorator Order

**WRONG** — `@handle_exceptions` before `@http_get`:
```python
@handle_exceptions()       # WRONG: must be after @http_get
@http_get("/")
def list_items(self, request):
    ...
```

**CORRECT** — HTTP method decorator is always first (outermost):
```python
@http_get("/")             # 1st: HTTP method
@handle_exceptions()       # 2nd: error handling
@log_api_call()            # 3rd: logging
def list_items(self, request):
    ...
```

---

## 9. Not Scoping Queries to User

**WRONG** — Returns all records:
```python
@http_get("/", response={200: list[NoteSchema]})
def list_notes(self, request):
    return 200, Note.objects.all()  # INSECURE: returns everyone's notes
```

**CORRECT** — Filter by authenticated user:
```python
@http_get("/", response={200: list[NoteSchema]})
def list_notes(self, request):
    return 200, Note.objects.filter(user=request.user)
```

---

## 10. Missing `__init__.py` Exports

**WRONG** — Creating files but not exporting:
```python
# notes/models/note.py exists but notes/models/__init__.py is empty
# Results in: ImportError: cannot import name 'Note' from 'notes.models'
```

**CORRECT** — Always export in `__init__.py`:
```python
# notes/models/__init__.py
from .note import Note

__all__ = ["Note"]
```

---

## 11. Using `ModelSerializer` or `from_attributes` Wrong

**WRONG** — Using DRF's ModelSerializer:
```python
class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = "__all__"
```

**WRONG** — Trying Django Ninja's `ModelSchema` (fragile, avoid it):
```python
class ItemSchema(ModelSchema):
    class Meta:
        model = Item
        fields = "__all__"
```

**CORRECT** — Explicit Pydantic schema:
```python
class ItemSchema(Schema):
    id: str
    name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## 12. Forgetting Controller Registration

**WRONG** — Creating a controller but only importing it:
```python
# notes/controllers/note_controller.py exists
# api/urls.py has: from notes.controllers import NoteController
# But NoteController is NOT in api.register_controllers()
# Result: endpoint doesn't show up
```

**CORRECT** — Import AND register:
```python
# api/urls.py
from notes.controllers import NoteController

api.register_controllers(
    # ... existing controllers ...
    NoteController,  # Must be explicitly listed here
)
```

---

## 13. Using `JsonResponse` or `HttpResponse`

**WRONG** — Raw Django responses:
```python
from django.http import JsonResponse

@http_get("/")
def list_items(self, request):
    items = list(Item.objects.values())
    return JsonResponse({"items": items})
```

**CORRECT** — Return tuple of (status_code, data):
```python
@http_get("/", response={200: list[ItemSchema]})
def list_items(self, request):
    return 200, Item.objects.filter(user=request.user)
```

---

## 14. Catching Exceptions Too Broadly

**WRONG** — Swallowing all errors:
```python
def create_item(self, request, payload):
    try:
        item = Item.objects.create(**payload.model_dump())
        return 201, item
    except Exception:
        return 400, {"error": "Something went wrong"}  # NO DETAILS, NO LOGGING
```

**CORRECT** — Use structured exceptions, let `@handle_exceptions` do its job:
```python
@http_post("/", response={201: ItemSchema, 400: dict})
@handle_exceptions()
def create_item(self, request, payload: CreateItemSchema):
    item = self.service.create_for_user(request.user, payload.model_dump())
    return 201, item
# If service raises ValidationError/NotFoundError, @handle_exceptions maps it to the right HTTP status
```

---

## 15. Creating Unnecessary Abstraction

**WRONG** — Over-engineering for one endpoint:
```python
# utils/query_builder.py
class QueryBuilder:
    def __init__(self, model):
        self.model = model
        self.filters = {}

    def with_user(self, user):
        self.filters["user"] = user
        return self

    def with_status(self, status):
        if status:
            self.filters["status"] = status
        return self

    def build(self):
        return self.model.objects.filter(**self.filters)
```

**CORRECT** — Just write the query:
```python
def get_user_items(self, user, status=None):
    qs = Item.objects.filter(user=user)
    if status:
        qs = qs.filter(status=status)
    return qs
```

---

## 16. Using Raw `Schema` Instead of `CamelCaseSchema`

**WRONG** — Raw Schema outputs snake_case JSON:
```python
from ninja import Schema

class NoteSchema(Schema):
    first_name: str
    last_name: str
    created_at: datetime

    class Config:
        from_attributes = True

# Output: {"first_name": "...", "last_name": "...", "created_at": "..."}
```

**CORRECT** — CamelCaseSchema auto-converts to camelCase:
```python
from core.schemas.base_schema import CamelCaseSchema

class NoteSchema(CamelCaseSchema):
    first_name: str
    last_name: str
    created_at: datetime
    # No Config needed — CamelCaseSchema already sets from_attributes = True

# Output: {"firstName": "...", "lastName": "...", "createdAt": "..."}
```

---

## 17. CRUDService.update() Takes an ID, Not an Instance

**WRONG** — Passing a model instance to update():
```python
note = Note.objects.get(id=note_id)
self.service.update(note, data)  # WRONG: first arg is ID, not instance
```

**CORRECT** — Pass the ID:
```python
self.service.update(note_id, data, user=request.user)
# Or use partial_update to skip None values:
self.service.partial_update(note_id, data, user=request.user)
```

---

## 18. Wrong Rate Limit Signature

**WRONG**:
```python
@rate_limit(rate=10, period=60)  # These params don't exist
```

**CORRECT**:
```python
@rate_limit(requests_per_minute=30)  # Actual parameter name
@rate_limit(requests_per_minute=30, key_func=custom_key)  # With custom key
```

---

## Summary Checklist

Before submitting code, verify:

- [ ] No `rest_framework` imports
- [ ] No `Router()` — using `@api_controller` instead
- [ ] No redeclared base model fields
- [ ] Business logic in services, not controllers
- [ ] Using `uv`, never `pip`
- [ ] Tests hit real DB, no mocking
- [ ] `@handle_exceptions()` on every controller method
- [ ] Decorator order: `@http_*` → `@handle_exceptions` → `@log_api_call`
- [ ] Queries scoped to `request.user`
- [ ] All `__init__.py` files export properly
- [ ] Controller imported AND registered in `api.register_controllers()` in `api/urls.py`
- [ ] Schemas inherit from `CamelCaseSchema`, not raw `Schema`
- [ ] No redundant `class Config: from_attributes = True` (CamelCaseSchema includes it)
- [ ] `service.update(id, data)` — pass ID, not instance
- [ ] `@rate_limit(requests_per_minute=N)` — correct parameter name
- [ ] Return `(status_code, data)` tuples, not `JsonResponse`
