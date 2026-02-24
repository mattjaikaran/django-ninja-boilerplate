# Django Ninja Boilerplate - Project Overview

This document provides a comprehensive overview of the project to help LLMs quickly understand and work with the codebase.

## Project Purpose

Django Ninja Boilerplate is a production-ready Django REST API boilerplate built with **Django Ninja Extra** for creating modern, high-performance APIs using **class-based controllers**. It provides authentication (JWT, magic links, OTP), background tasks (Celery), caching (Redis), and comprehensive tooling for rapid API development.

## Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.13+ |
| Framework | Django | 6.0+ |
| API Framework | Django Ninja Extra | 0.30+ |
| Authentication | Django Ninja JWT | 5.3+ |
| Database | PostgreSQL | 15+ |
| Cache/Broker | Redis | 7+ |
| Task Queue | Celery | 5.4+ |
| Real-Time | Centrifugo | 5+ |
| Package Manager | uv | latest |
| Linting/Formatting | Ruff | 0.7+ |
| Testing | pytest + Factory Boy | - |
| Admin | Django Unfold | - |

## Directory Structure

```
django-ninja-boilerplate/
├── api/                          # Main Django project configuration
│   ├── settings/                 # Split settings (common.py, dev.py, prod.py)
│   ├── celery.py                 # Celery configuration
│   ├── centrifugo.py             # Centrifugo JWT tokens + HTTP client
│   ├── decorators.py             # API decorators (@handle_exceptions, @log_api_call)
│   ├── exceptions.py             # Custom exception classes
│   ├── healthcheck.py            # Health check controller
│   ├── middleware.py             # Custom middleware
│   ├── pagination/               # Pagination utilities (offset, cursor)
│   ├── permissions.py            # Permission classes
│   ├── throttling/               # Rate limiting utilities
│   ├── urls.py                   # URL configuration and controller registration
│   └── utils/                    # HTTP utilities, validation helpers
│
├── core/                         # Core app (users, authentication)
│   ├── admin/                    # Admin configurations (user_admin.py)
│   ├── cache/                    # Caching utilities and decorators
│   ├── controllers/              # API controllers
│   │   ├── auth_controller.py    # Login, signup, magic links
│   │   ├── centrifugo_controller.py # Real-time token endpoints
│   │   ├── otp_controller.py     # OTP/2FA endpoints
│   │   └── users_controller.py   # User CRUD endpoints
│   ├── management/commands/      # Django management commands
│   │   └── generators/           # Feature generation templates
│   ├── models/                   # Database models
│   │   ├── base.py               # AbstractBaseModel, SoftDeleteModel
│   │   ├── user.py               # Custom User model
│   │   └── otp.py                # OneTimePassword model
│   ├── monitoring/               # Performance metrics
│   ├── schemas/                  # Pydantic schemas
│   │   ├── auth_schema.py        # Auth request/response schemas
│   │   ├── base_schema.py        # Common schemas (MessageResponse)
│   │   ├── otp_schema.py         # OTP schemas
│   │   └── user_schema.py        # User schemas
│   ├── services/                 # Business logic layer
│   │   ├── base_service.py       # BaseService, CRUDService classes
│   │   ├── email/                # Email service
│   │   └── otp_service.py        # OTP service
│   ├── tasks.py                  # Celery tasks
│   └── tests/                    # Tests
│       └── factories/            # Test factories (UserFactory)
│
├── todos/                        # Example app demonstrating patterns
│   ├── admin/                    # Todo admin
│   ├── controllers/              # Todo controller
│   ├── models/                   # Todo model
│   ├── schemas/                  # Todo schemas
│   └── tests/                    # Todo tests with factories
│
├── cli/                          # CLI tool for project scaffolding
├── deploy/                       # Deployment configurations
│   ├── centrifugo/               # Centrifugo server config
│   ├── docker/                   # Docker configurations
│   ├── kubernetes/               # Helm charts
│   └── paas/                     # Railway, Render configs
│
├── conftest.py                   # Global pytest fixtures
├── docker-compose.yml            # Development Docker setup
├── docker-compose.prod.yml       # Production Docker setup
├── Makefile                      # Development commands
└── pyproject.toml                # Project configuration
```

## Key Patterns

### 1. Controllers (API Endpoints)

Controllers use Django Ninja Extra's `@api_controller` decorator with class-based structure:

```python
from ninja_extra import api_controller, http_get, http_post, http_put, http_delete
from api.decorators import handle_exceptions, log_api_call

@api_controller("/items", tags=["Items"])
class ItemController:
    @http_get("/", response={200: list[ItemSchema]})
    @handle_exceptions()
    @log_api_call()
    def list_items(self, request):
        """List all items for the authenticated user."""
        return 200, Item.objects.filter(user=request.user)

    @http_post("/", response={201: ItemSchema, 400: dict})
    @handle_exceptions()
    @log_api_call(include_payload=True)
    def create_item(self, request, payload: CreateItemSchema):
        """Create a new item."""
        item = Item.objects.create(user=request.user, **payload.model_dump())
        return 201, item
```

### 2. Models

All models inherit from `AbstractBaseModel` or `SoftDeleteModel`:

```python
from core.models import AbstractBaseModel, SoftDeleteModel

class MyModel(SoftDeleteModel):
    """Model with soft delete support."""

    # Custom fields
    name = models.CharField(max_length=255)

    # Automatically includes from AbstractBaseModel:
    # - id (UUID primary key)
    # - created_at (DateTimeField, auto_now_add)
    # - updated_at (DateTimeField, auto_now)
    # - created_by (ForeignKey to User)
    # - updated_by (ForeignKey to User)
    # - is_active (Boolean, for soft delete)
    # - metadata (JSONField)

    class Meta:
        verbose_name = "My Model"
        verbose_name_plural = "My Models"
```

### 3. Schemas (Pydantic)

Request and response validation using Pydantic schemas:

```python
from ninja import Schema
from pydantic import Field, EmailStr, field_validator
from datetime import datetime

# Response schema
class ItemSchema(Schema):
    id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Enable ORM mode

# Create schema
class CreateItemSchema(Schema):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

# Update schema (all fields optional)
class UpdateItemSchema(Schema):
    name: str | None = None
    description: str | None = None
```

### 4. Services (Business Logic)

Services encapsulate business logic and extend `CRUDService`:

```python
from core.services.base_service import CRUDService
from myapp.models import MyModel

class MyModelService(CRUDService[MyModel]):
    model = MyModel

    def get_queryset(self):
        """Override to add default filters or select_related."""
        return super().get_queryset().select_related("user")

    def custom_business_logic(self, data: dict, user) -> MyModel:
        """Custom business logic method."""
        # Validation, transformation, etc.
        return self.create(data, user=user)
```

### 5. Decorators

Use provided decorators for consistent error handling:

```python
from api.decorators import handle_exceptions, log_api_call, validate_request

@http_post("/")
@handle_exceptions(return_500_on_error=True, log_errors=True)
@log_api_call(include_payload=True, include_response=False)
@validate_request()  # Optional custom validators
def create_item(self, request, payload: CreateItemSchema):
    ...
```

## Common Tasks

### Starting the Development Server

```bash
# With Docker (recommended)
make up                  # Start db, redis, django
make up-celery          # Start with Celery workers
make up-realtime        # Start with Centrifugo
make up-full            # Start all services

# Without Docker
make local-run          # Run Django locally
```

### Running Tests

```bash
make test               # Run all tests
make test-coverage      # Run with coverage report
uv run pytest -k "test_auth"  # Run specific tests
uv run pytest -v        # Verbose output
```

### Creating Migrations

```bash
make makemigrations     # Create new migrations
make migrate            # Apply migrations
```

### Adding a New App

```bash
make startapp APP=myapp  # Create new app with proper structure
```

### Generating Features

```bash
make generate-feature FEATURE=payments PROVIDER=stripe
make generate-feature FEATURE=rbac PLATFORM=b2b
```

### Linting and Formatting

```bash
make lint               # Run ruff linter
make format             # Format code with ruff
```

## Testing Patterns

### Test Structure

Tests use pytest with Factory Boy for data generation:

```python
import pytest
from core.tests.factories import UserFactory
from myapp.tests.factories import MyModelFactory

@pytest.mark.django_db
class TestMyModelAPI:
    def test_create_item(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(
            "/api/items/",
            {"name": "Test Item"},
            content_type="application/json"
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Test Item"

    def test_list_items(self, authenticated_client, user):
        client, user = authenticated_client
        MyModelFactory.create_batch(3, user=user)
        response = client.get("/api/items/")
        assert response.status_code == 200
        assert len(response.json()) == 3
```

### Fixtures (from conftest.py)

- `user` - Regular test user
- `staff_user` - Staff user
- `superuser` - Superuser
- `api_client` - Django test client
- `auth_headers` - JWT auth headers
- `authenticated_client` - Tuple of (client, user) with auth

### Factory Pattern

```python
import factory
from myapp.models import MyModel
from core.tests.factories import UserFactory

class MyModelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MyModel

    name = factory.Faker("sentence", nb_words=3)
    user = factory.SubFactory(UserFactory)
    created_by = factory.SelfAttribute("user")
```

## Deployment Options

### 1. Docker Compose (Development)

```bash
make up                 # Development
make prod-up           # Production with Nginx
```

### 2. PaaS (Railway, Render, Fly.io)

```bash
make single-build       # Build single container
railway up              # Deploy to Railway
```

### 3. Kubernetes

```bash
helm install my-api ./deploy/kubernetes/helm/django-ninja-stack
```

## API Documentation

- Swagger UI: http://localhost:8000/api/docs
- Admin Panel: http://localhost:8000/admin

## Key Files to Reference

| Purpose | File |
|---------|------|
| Controller example | `todos/controllers/todo_controller.py` |
| Model example | `todos/models/todo.py` |
| Schema example | `todos/schemas/todo_schema.py` |
| Service base | `core/services/base_service.py` |
| Base models | `core/models/base.py` |
| Test example | `todos/tests/test_todo.py` |
| Factory example | `core/tests/factories/user_factory.py` |
| Celery tasks | `core/tasks.py` |
| Centrifugo client | `api/centrifugo.py` |
| Centrifugo tokens | `core/controllers/centrifugo_controller.py` |
| API decorators | `api/decorators.py` |
| Exceptions | `api/exceptions.py` |
| URL routing | `api/urls.py` |
| Global fixtures | `conftest.py` |
