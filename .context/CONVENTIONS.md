# Coding Conventions and Patterns

This document describes the coding conventions, naming patterns, and best practices used in this Django Ninja boilerplate.

---

## Naming Conventions

### Files and Directories

| Type | Convention | Example |
|------|------------|---------|
| App directories | `lowercase_snake_case` | `todos/`, `user_profiles/` |
| Model files | `lowercase_snake_case.py` | `todo.py`, `user_profile.py` |
| Schema files | `lowercase_snake_case.py` | `todo_schema.py` |
| Controller files | `lowercase_snake_case.py` | `todo_controller.py` |
| Service files | `lowercase_snake_case.py` | `todo_service.py` |
| Test files | `test_lowercase_snake_case.py` | `test_todo.py` |
| Factory files | `lowercase_factory.py` | `todo_factory.py` |

### Python Classes

| Type | Convention | Example |
|------|------------|---------|
| Models | `PascalCase` | `Todo`, `UserProfile` |
| Schemas | `PascalCase` + `Schema` suffix | `TodoSchema`, `CreateTodoSchema` |
| Controllers | `PascalCase` + `Controller` suffix | `TodoController` |
| Services | `PascalCase` + `Service` suffix | `TodoService` |
| Factories | `PascalCase` + `Factory` suffix | `TodoFactory` |
| Exceptions | `PascalCase` + `Error` suffix | `ValidationError`, `NotFoundError` |

### Functions and Methods

| Type | Convention | Example |
|------|------------|---------|
| Functions | `lowercase_snake_case` | `get_user_todos()` |
| Private methods | `_lowercase_snake_case` | `_validate_input()` |
| Constants | `UPPERCASE_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_PAGE_SIZE` |

### Variables

| Type | Convention | Example |
|------|------------|---------|
| Local variables | `lowercase_snake_case` | `user_data`, `todo_list` |
| Class attributes | `lowercase_snake_case` | `model`, `queryset` |
| Boolean variables | `is_` or `has_` prefix | `is_active`, `has_permission` |

### URL Patterns

| Type | Convention | Example |
|------|------------|---------|
| Collection endpoints | Plural noun | `/todos`, `/users` |
| Single resource | `/{resource_id}` | `/todos/{todo_id}` |
| Actions | Verb or noun describing action | `/todos/completed`, `/auth/login` |
| Nested resources | `/{parent}/{parent_id}/{child}` | `/users/{user_id}/todos` |

---

## File Organization

### App Structure

Every Django app should follow this structure:

```
myapp/
├── __init__.py
├── apps.py
├── admin/
│   ├── __init__.py
│   └── mymodel_admin.py
├── controllers/
│   ├── __init__.py
│   └── mymodel_controller.py
├── management/
│   ├── __init__.py
│   └── commands/
│       ├── __init__.py
│       └── my_command.py
├── migrations/
│   └── __init__.py
├── models/
│   ├── __init__.py
│   └── mymodel.py
├── schemas/
│   ├── __init__.py
│   └── mymodel_schema.py
├── services/
│   ├── __init__.py
│   └── mymodel_service.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── factories/
    │   ├── __init__.py
    │   └── mymodel_factory.py
    └── test_mymodel.py
```

### Module Exports (__init__.py)

Always export public classes/functions in `__init__.py`:

```python
# models/__init__.py
from .mymodel import MyModel

__all__ = ["MyModel"]
```

```python
# schemas/__init__.py
from .mymodel_schema import MyModelSchema, CreateMyModelSchema, UpdateMyModelSchema

__all__ = ["MyModelSchema", "CreateMyModelSchema", "UpdateMyModelSchema"]
```

```python
# controllers/__init__.py
from .mymodel_controller import MyModelController

__all__ = ["MyModelController"]
```

---

## Import Ordering

Imports should be organized in this order (Ruff enforces this):

```python
# 1. Future imports
from __future__ import annotations

# 2. Standard library imports
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

# 3. Third-party imports
from django.conf import settings
from django.db import models
from ninja import Schema
from pydantic import Field

# 4. First-party imports (project apps)
from core.models import AbstractBaseModel
from core.services.base_service import CRUDService

# 5. Local imports
from .mymodel import MyModel
```

### Import Best Practices

```python
# GOOD: Specific imports
from django.db import models
from ninja_extra import api_controller, http_get, http_post

# AVOID: Wildcard imports (except in __init__.py for re-exports)
from django.db.models import *

# GOOD: Group related imports
from api.decorators import handle_exceptions, log_api_call, validate_request

# GOOD: Alias for clarity when needed
from django.contrib.auth import get_user_model
User = get_user_model()
```

---

## Error Handling Patterns

### Custom Exceptions

Use the custom exception classes from `api/exceptions.py`:

```python
from api.exceptions import (
    ValidationError,      # 400 - Bad request
    AuthenticationError,  # 401 - Not authenticated
    APIPermissionError,   # 403 - Forbidden
    NotFoundError,        # 404 - Not found
    ConflictError,        # 409 - Conflict
    RateLimitError,       # 429 - Too many requests
    ExternalServiceError, # 502 - External service failed
)

# Usage
if not user.is_active:
    raise ValidationError(
        message="Account is disabled",
        code="account_disabled",
        details={"user_id": str(user.id)}
    )
```

### Controller Error Handling

```python
@api_controller("/items", tags=["Items"])
class ItemController:
    @http_get("/{item_id}", response={200: ItemSchema, 404: dict})
    @handle_exceptions()  # Always use this decorator
    def get_item(self, request, item_id: str):
        item = get_object_or_404(Item, id=item_id, user=request.user)
        return 200, item

    @http_post("/", response={201: ItemSchema, 400: dict, 500: dict})
    @handle_exceptions(return_500_on_error=True, log_errors=True)
    @log_api_call(include_payload=True)
    def create_item(self, request, payload: CreateItemSchema):
        # Validation errors are automatically handled by Pydantic
        item = Item.objects.create(user=request.user, **payload.model_dump())
        return 201, item
```

### Service Error Handling

```python
from api.exceptions import NotFoundError, ValidationError

class ItemService(CRUDService[Item]):
    model = Item

    def get_by_id_or_raise(self, id: str | UUID) -> Item:
        """Get item or raise NotFoundError."""
        item = self.get_by_id(id)
        if item is None:
            raise NotFoundError(
                message=f"Item with id {id} not found",
                code="item_not_found"
            )
        return item

    def create_with_validation(self, data: dict, user) -> Item:
        """Create with additional business validation."""
        if self.count(user=user) >= MAX_ITEMS_PER_USER:
            raise ValidationError(
                message="Maximum items limit reached",
                code="limit_exceeded",
                details={"max_items": MAX_ITEMS_PER_USER}
            )
        return self.create(data, user=user)
```

---

## Response Format Patterns

### Success Responses

```python
# Single resource
@http_get("/{id}", response={200: ItemSchema})
def get_item(self, request, id: str):
    item = get_object_or_404(Item, id=id)
    return 200, item  # Returns ItemSchema

# List of resources
@http_get("/", response={200: list[ItemSchema]})
def list_items(self, request):
    items = Item.objects.filter(user=request.user)
    return 200, items  # Returns list[ItemSchema]

# Create resource
@http_post("/", response={201: ItemSchema})
def create_item(self, request, payload: CreateSchema):
    item = Item.objects.create(**payload.model_dump())
    return 201, item  # Returns 201 with ItemSchema

# Update resource
@http_put("/{id}", response={200: ItemSchema})
def update_item(self, request, id: str, payload: UpdateSchema):
    item = get_object_or_404(Item, id=id)
    for attr, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, attr, value)
    item.save()
    return 200, item

# Delete resource
@http_delete("/{id}", response={204: None})
def delete_item(self, request, id: str):
    item = get_object_or_404(Item, id=id)
    item.delete()
    return 204, None  # No content
```

### Error Responses

```python
# Standard error response format
{
    "error": True,
    "message": "Human-readable error message",
    "code": "machine_readable_code",
    "details": {
        "field": "additional context"
    }
}

# Validation error with field errors
{
    "error": True,
    "message": "Validation failed",
    "code": "validation_error",
    "field_errors": {
        "email": ["Invalid email format"],
        "password": ["Password too short"]
    }
}
```

### Message Response Pattern

```python
from core.schemas import MessageResponse

@http_post("/action", response={200: MessageResponse})
def perform_action(self, request):
    # ... perform action
    return 200, {"message": "Action completed successfully", "success": True}
```

---

## Schema Patterns

### Response Schema

```python
from ninja import Schema
from datetime import datetime

class ItemSchema(Schema):
    """Response schema for Item."""
    id: str
    name: str
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Enable ORM mode
```

### Create Schema

```python
from ninja import Schema
from pydantic import Field, field_validator

class CreateItemSchema(Schema):
    """Schema for creating an Item."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    status: str = Field("draft", pattern="^(draft|active|completed)$")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip()
```

### Update Schema (All Optional)

```python
class UpdateItemSchema(Schema):
    """Schema for updating an Item. All fields optional."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None."""
        if v == "":
            return None
        return v
```

### Nested Schema

```python
class UserBasicSchema(Schema):
    """Minimal user info for embedding."""
    id: str
    email: str
    username: str

    class Config:
        from_attributes = True

class ItemWithUserSchema(ItemSchema):
    """Item with embedded user info."""
    user: UserBasicSchema
```

---

## Model Patterns

### Standard Model

```python
from django.conf import settings
from django.db import models
from core.models import SoftDeleteModel

class Item(SoftDeleteModel):
    """Item model with soft delete support."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="items"
    )

    # Fields
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="medium"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Item"
        verbose_name_plural = "Items"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["user", "status"]),
        ]
```

### Model with Custom Manager

```python
class PublishedManager(models.Manager):
    """Manager for published items only."""
    def get_queryset(self):
        return super().get_queryset().filter(status="published")

class Article(SoftDeleteModel):
    # ... fields ...

    objects = models.Manager()  # Default manager
    published = PublishedManager()  # Custom manager

    # Usage: Article.published.all()
```

---

## Controller Patterns

### Standard CRUD Controller

```python
import logging
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put
from ninja_extra.pagination import paginate

from api.decorators import handle_exceptions, log_api_call

logger = logging.getLogger(__name__)

@api_controller("/items", tags=["Items"])
class ItemController:
    """Controller for Item CRUD operations."""

    @paginate
    @http_get("/", response={200: list[ItemSchema]})
    @handle_exceptions()
    @log_api_call()
    def list_items(
        self,
        request,
        status: str | None = None,
        search: str | None = None,
    ):
        """List items with filtering."""
        queryset = Item.objects.filter(user=request.user)

        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(name__icontains=search)

        return 200, queryset

    @http_get("/{item_id}", response={200: ItemSchema, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def get_item(self, request, item_id: str):
        """Get a single item by ID."""
        return 200, get_object_or_404(Item, id=item_id, user=request.user)

    @http_post("/", response={201: ItemSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_item(self, request, payload: CreateItemSchema):
        """Create a new item."""
        item = Item.objects.create(
            user=request.user,
            **payload.model_dump()
        )
        logger.info("Created item %s for user %s", item.id, request.user.id)
        return 201, item

    @http_put("/{item_id}", response={200: ItemSchema, 404: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def update_item(self, request, item_id: str, payload: UpdateItemSchema):
        """Update an existing item."""
        item = get_object_or_404(Item, id=item_id, user=request.user)

        for attr, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, attr, value)
        item.save()

        return 200, item

    @http_delete("/{item_id}", response={204: None, 404: dict})
    @handle_exceptions()
    @log_api_call()
    def delete_item(self, request, item_id: str):
        """Delete an item."""
        item = get_object_or_404(Item, id=item_id, user=request.user)
        item.delete()  # Or item.soft_delete(user=request.user)
        return 204, None
```

---

## Test Patterns

### Test Class Structure

```python
import pytest
from core.tests.factories import UserFactory
from myapp.tests.factories import ItemFactory
from myapp.models import Item

@pytest.mark.django_db
class TestItemModel:
    """Unit tests for Item model."""

    def test_create_item(self, user):
        item = ItemFactory(user=user)
        assert item.name
        assert item.user == user

    def test_item_str(self, user):
        item = ItemFactory(user=user, name="Test Item")
        assert str(item) == "Test Item"

    def test_soft_delete(self, user):
        item = ItemFactory(user=user)
        item.soft_delete()
        assert not item.is_active
        assert Item.objects.filter(id=item.id).count() == 0
        assert Item.all_objects.filter(id=item.id).count() == 1


@pytest.mark.django_db
class TestItemAPI:
    """Integration tests for Item API."""

    def test_create_item(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(
            "/api/items/",
            {"name": "New Item"},
            content_type="application/json"
        )
        assert response.status_code == 201
        assert Item.objects.filter(user=user).exists()

    def test_list_items_only_own(self, authenticated_client):
        client, user = authenticated_client
        ItemFactory.create_batch(3, user=user)

        # Other user's items
        other_user = UserFactory()
        ItemFactory.create_batch(2, user=other_user)

        response = client.get("/api/items/")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 3

    def test_unauthorized_access(self, api_client):
        response = api_client.get("/api/items/")
        assert response.status_code == 401
```

### Factory Pattern

```python
import factory
from myapp.models import Item
from core.tests.factories import UserFactory

class ItemFactory(factory.django.DjangoModelFactory):
    """Factory for creating Item instances."""

    class Meta:
        model = Item

    name = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("text", max_nb_chars=200)
    status = "draft"
    user = factory.SubFactory(UserFactory)
    created_by = factory.SelfAttribute("user")
    updated_by = factory.SelfAttribute("user")

class ActiveItemFactory(ItemFactory):
    """Factory for active items."""
    status = "active"

class CompletedItemFactory(ItemFactory):
    """Factory for completed items."""
    status = "completed"
```

---

## Logging Patterns

```python
import logging

logger = logging.getLogger(__name__)

# Info for successful operations
logger.info("Created item %s for user %s", item.id, user.id)

# Warning for non-critical issues
logger.warning("Rate limit approaching for user %s", user.id)

# Error for failures (with exception info)
logger.exception("Failed to create item: %s", str(e))

# Debug for detailed troubleshooting
logger.debug("Processing payload: %s", payload.model_dump())
```

---

## Code Style Rules

### Ruff Configuration (pyproject.toml)

- Line length: 88 characters
- Target Python: 3.12+
- Docstring style: Google
- Quote style: Double quotes

### Docstring Format

```python
def process_item(item_id: str, user: User, options: dict | None = None) -> Item:
    """Process an item with the given options.

    Args:
        item_id: The UUID of the item to process.
        user: The user performing the action.
        options: Optional processing options.

    Returns:
        The processed item instance.

    Raises:
        NotFoundError: If the item doesn't exist.
        ValidationError: If the options are invalid.
    """
```

### Type Hints

Always use type hints:

```python
# Functions
def get_user_items(user: User, status: str | None = None) -> QuerySet[Item]:
    ...

# Class attributes
class ItemService:
    model: type[Item]

# Variables (when not obvious)
items: list[Item] = []
result: dict[str, Any] = {}
```
