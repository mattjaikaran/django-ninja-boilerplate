---
description: WRONG vs. CORRECT code for common LLM mistakes here (DRF, raw Schema, logic in controllers, decorator order, unscoped queries, CRUDService.update, throttling)
globs: ["**/*.py"]
---

# Anti-patterns

Each item shows WRONG code, then CORRECT code. The rules are in `AGENTS.md`;
the base-class details are in
`.agents/skills/django-ninja-dev/references/layer-reference.md`.

## 1. DRF imports: banned

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

## 2. Router function-based views: banned

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

## 3. Raw `Schema` instead of `CamelCaseSchema`: banned

A raw `Schema` returns snake_case keys. `CamelCaseSchema` returns camelCase
keys and already sets `from_attributes = True`.

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

## 4. `ModelSchema`: banned

WRONG:
```python
from ninja import ModelSchema

class ItemSchema(ModelSchema):
    class Meta:
        model = Item
        fields = "__all__"
```

CORRECT: write an explicit Pydantic schema that inherits `CamelCaseSchema`.

## 5. Redeclared base model fields: banned

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

## 6. Business logic in controllers: banned

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

CORRECT: the controller calls the service.
```python
@api_controller("/orders", tags=["Orders"], auth=JWTAuth())
class OrderController:
    def __init__(self):
        self.service = OrderService()

    @http_post("/", response={201: OrderSchema, 400: dict})
    @log_api_call(include_payload=True)
    def create_order(self, request, payload: CreateOrderSchema):
        return 201, self.service.create_order(payload, request.user)
```

## 7. Importing `handle_exceptions`: error

WRONG: the decorator does not exist.
```python
from api.decorators import handle_exceptions

@http_get("/{item_id}", response={200: ItemSchema})
@handle_exceptions()
def get_item(self, request, item_id: str):
    return 200, get_object_or_404(Item, id=item_id)
```

CORRECT: the handlers in `api/urls.py` map exceptions to responses.
```python
@http_get("/{item_id}", response={200: ItemSchema, 404: dict})
@log_api_call()
def get_item(self, request, item_id: str):
    item = get_object_or_404(Item, id=item_id, user=request.user)
    return 200, item
```

## 8. Wrong decorator order

WRONG:
```python
@log_api_call()            # WRONG: must be after @http_get
@http_get("/")
def list_items(self, request):
    ...
```

CORRECT: the HTTP method decorator is always outermost.
```python
@http_get("/")             # 1st: HTTP method
@log_api_call()            # 2nd: logging
@paginate(PageNumberPaginationExtra)  # 3rd: list endpoints only
def list_items(self, request):
    ...
```

## 9. Unscoped queries: security bug

WRONG:
```python
return 200, Note.objects.all()  # Returns EVERYONE'S notes
```

CORRECT:
```python
return 200, Note.objects.filter(user=request.user)
```

## 10. Missing `__init__.py` exports

WRONG: an empty `__init__.py`.
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

## 11. Mocking the database in tests: banned

WRONG:
```python
def test_create_item(mocker):
    mock_create = mocker.patch("items.models.Item.objects.create")
    mock_create.return_value = Item(id="fake-id")
```

CORRECT: use the real database.
```python
def test_create_item(authenticated_client):
    client, user = authenticated_client
    response = client.post("/api/items/", {"name": "Test"}, content_type="application/json")
    assert response.status_code == 201
    assert Item.objects.filter(user=user, name="Test").exists()
```

Also banned: model tests (`__str__`, field defaults), unit tests per function,
tests that assert on mocks, and tests written for coverage. See "Testing
policy" in `AGENTS.md`.

## 12. pip, npm, yarn: banned

WRONG: `pip install django-ninja`, `npm install react`, `yarn add typescript`
CORRECT: `uv add django-ninja`, `bun add react`, `bun add typescript`

## 13. `JsonResponse` or `HttpResponse` from an endpoint

A raw Django response skips the response schema and the OpenAPI contract.

WRONG:
```python
from django.http import JsonResponse

@http_get("/")
def list_items(self, request):
    return JsonResponse({"items": list(Item.objects.values())})
```

CORRECT: return a `(status_code, data)` tuple.
```python
@http_get("/", response={200: list[ItemSchema]})
def list_items(self, request):
    return 200, self.service.list_items(request.user)
```

## 14. Catching exceptions too broadly

WRONG: the client gets no detail and the log gets no traceback.
```python
def create_item(self, request, payload: CreateItemSchema):
    try:
        return 201, self.service.create_item(payload, request.user)
    except Exception:
        return 400, {"error": "Something went wrong"}
```

CORRECT: let `api.exceptions` errors propagate to the handlers in
`api/urls.py`. Catch only a specific exception, and raise it again with the
real message.
```python
# service
try:
    charge = provider.charge(amount)
except ProviderTimeout as exc:
    raise ExternalServiceError(message=str(exc)) from exc
```

## 15. Abstraction before a second use case

WRONG: a builder class for one query.
```python
class QueryBuilder:
    def __init__(self, model):
        self.model = model
        self.filters = {}

    def with_user(self, user):
        self.filters["user"] = user
        return self

    def build(self):
        return self.model.objects.filter(**self.filters)
```

CORRECT: write the query in the service.
```python
def list_items(self, user, status: str | None = None):
    qs = Item.objects.filter(user=user)
    if status:
        qs = qs.filter(status=status)
    return qs
```

## 16. Passing an instance to `CRUDService.update()`

`update()`, `partial_update()` and `delete()` take an ID. Their `user`
argument fills audit fields only; it does not check the owner.

WRONG:
```python
note = Note.objects.get(id=note_id)
self.update(note, data)          # first argument is an ID
self.update(note_id, data, user=user)  # no ownership check
```

CORRECT: check the owner, then pass the ID.
```python
def update_note(self, note_id: str, data: dict, user) -> Note:
    get_object_or_404(Note, id=note_id, user=user)
    return self.update(note_id, data, user=user)
```

## 17. Inventing a rate-limit decorator

WRONG: `@rate_limit` does not exist in this repository.
```python
@rate_limit(requests_per_minute=30)
def signup(self, request, payload: UserSignupSchema):
    ...
```

CORRECT: use `throttle` from `ninja_extra.throttling` with a scope from
`NINJA_EXTRA["THROTTLE_RATES"]` in `api/settings/common.py`.
```python
from ninja_extra.throttling import DynamicRateThrottle, throttle

@http_post("/signup", response={202: MessageResponse, 400: dict}, auth=None)
@throttle(DynamicRateThrottle, scope="anon-email")
@log_api_call()
def signup(self, request, payload: UserSignupSchema):
    ...
```
