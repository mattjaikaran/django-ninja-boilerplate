# Django Ninja Boilerplate

A production-ready, **opinionated** Django boilerplate built with **Django Ninja Extra** for creating modern REST APIs using **class-based controllers** (not function views). This project provides everything you need to quickly build scalable APIs with authentication, caching, monitoring, background tasks, and automated feature generation.

> **This is an opinionated boilerplate.** Every tool, pattern, and layer of abstraction was chosen deliberately — `uv` over pip/poetry, `ruff` over flake8/black, `uuidv7` PKs, class-based controllers over function views, a service layer for business logic, and a decorator system for cross-cutting concerns. If you disagree with a choice, it is easy to remove, but each default was selected for a reason.

> The `todos` app ships four controller variants — from maximum verbosity to full service-layer abstraction - all can perform the same operations with different levels of abstraction.

> **Architecture Note:** This boilerplate uses [Django Ninja Extra](https://eadwincode.github.io/django-ninja-extra/) which extends Django Ninja with class-based API controllers, dependency injection, and permissions. Instead of function-based views, you write clean controller classes with decorators like `@api_controller` and `@http_get`.

[![CI](https://github.com/mattjaikaran/django-ninja-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/mattjaikaran/django-ninja-boilerplate/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-green.svg)](https://docs.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539.svg)](https://swagger.io/specification/)

## Why This Boilerplate?

| Feature                          | Benefit                                                                     |
| -------------------------------- | --------------------------------------------------------------------------- |
| **One-command setup**            | `make setup` gets you from clone to running in under 2 minutes              |
| **Class-based controllers**      | Clean, organized API code with Django Ninja Extra                           |
| **Enterprise features built-in** | Audit logging, feature flags, observability - no need to add later          |
| **Multiple auth methods**        | JWT, magic links, OTP codes, 2FA, API keys - ready for web, mobile, and M2M |
| **Full observability**           | Distributed tracing, metrics, structured logging out of the box             |
| **SDK generation**               | Auto-generate TypeScript and Python clients from your API                   |
| **Production-ready**             | Docker, K8s Helm charts, PaaS configs - deploy anywhere                     |
| **Test everything**              | Unit, E2E, contract, and load tests included                                |
| **Progressive patterns**         | Four `todos` controller variants show every abstraction level side-by-side  |

## Progressive Controller Patterns

The `todos` app ships **four controller variants** so you can compare approaches and pick the one that fits your team. All four expose the same CRUD surface area — only the implementation style differs.

| #   | Pattern                  | Route Prefix              | File                             | When to Use                                                                                   |
| --- | ------------------------ | ------------------------- | -------------------------------- | --------------------------------------------------------------------------------------------- |
| 1   | **Declarative**          | `/api/todos-declarative/` | `todo_controller_declarative.py` | Learning the framework; teams that want every error path explicit with no decorator magic     |
| 2   | **Basic**                | `/api/todos-basic/`       | `todo_controller_basic.py`       | Small projects; minimal abstraction with `get_object_or_404`                                  |
| 3   | **Partial**              | `/api/todos-partial/`     | `todo_controller_partial.py`     | Mix-and-match: reads are plain, writes use `handle_exceptions` + `log_api_call`               |
| 4   | **Full (service layer)** | `/api/todos/`             | `todo_controller.py`             | **Recommended for production.** Controller is a thin HTTP adapter; all logic in `TodoService` |

```python
# Pattern 1 — Declarative: every error path is explicit
def create_todo(self, request, payload: CreateTodoSchema):
    try:
        todo_data = payload.model_dump()
        todo_data["user"] = request.user
        todo = Todo.objects.create(**todo_data)
        logger.info("Created todo '%s'", todo.title)
        return 201, todo
    except Exception as exc:
        logger.exception("Failed to create todo")
        return 500, {"error": "Error creating todo", "detail": str(exc)}

# Pattern 2 — Basic: minimal, let Django handle errors
def create_todo(self, request, payload: CreateTodoSchema):
    todo_data = payload.model_dump()
    todo_data["user"] = request.user
    return 201, Todo.objects.create(**todo_data)

# Pattern 3 — Partial: decorators on writes only
@http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
@log_api_call(include_payload=True, include_response=False)
@handle_exceptions(return_500_on_error=True, log_errors=True)
def create_todo(self, request, payload: CreateTodoSchema):
    todo_data = payload.model_dump()
    todo_data["user"] = request.user
    return 201, Todo.objects.create(**todo_data)

# Pattern 4 — Service layer: controller is a thin HTTP adapter
class TodoController:
    def __init__(self):
        self.service = TodoService()

    @http_post("/", response={201: TodoSchema, 400: dict, 500: dict})
    @log_api_call(include_payload=True, include_response=False)
    @handle_exceptions(return_500_on_error=True, log_errors=True)
    @validate_request()
    def create_todo(self, request, payload: CreateTodoSchema):
        return 201, self.service.create_todo(payload, request.user)
```

The `TodoService` (`todos/services/todo_service.py`) centralises all business logic — filtering, ordering, ORM calls, and 404 handling — so it can be shared across controllers and tested independently without HTTP context. See [`todos/README.md`](todos/README.md) for full details on each pattern.

## Architecture Overview

```
                                    ┌─────────────────┐
                                    │   Clients       │
                                    │ Web/Mobile/API  │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
           ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
           │  REST API   │          │   GraphQL   │          │  WebSocket  │
           │ Django Ninja│          │  Strawberry │          │ Centrifugo  │
           └──────┬──────┘          └──────┬──────┘          └──────┬──────┘
                  │                        │                        │
                  └────────────┬───────────┘          publish via   │
                               │                      HTTP API ─────┘
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌─────────────┐     ┌─────────────┐     ┌──────────────┐
    │   Auth      │     │  Features   │     │ Observability│
    │ JWT/OTP/2FA │     │ Flags/Audit │     │ Traces/Metrics│
    └─────────────┘     └─────────────┘     └──────────────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │ PostgreSQL  │     │   Valkey    │     │   Celery    │
    │  Database   │     │ Cache/Queue │     │   Workers   │
    └─────────────┘     └─────────────┘     └─────────────┘
```

## What's Included

This boilerplate gives you a solid foundation with:

- **Authentication System** - JWT-based auth with:
  - Traditional email/password login
  - Passwordless magic links
  - **6-digit OTP codes** for mobile/iOS apps (SMS, email, push)
  - Two-factor authentication (2FA)
  - Rate limiting and brute force protection
- **Service Layer Architecture** - Clean separation of business logic with base service classes
- **Email Service** - Template-based email system with multiple backend support
- **Caching Layer** - Valkey (Redis-compatible) integration with decorators for easy caching
- **Real-Time Messaging** - [Centrifugo](https://centrifugal.dev/) WebSocket server with JWT auth, channel namespaces, presence, and history
- **Background Tasks** - Celery integration with Valkey broker and Flower monitoring
- **Monitoring Tools** - Performance tracking and health check endpoints
- **Database Management** - Comprehensive dump/restore commands and SQL init scripts
- **Data Seeding** - Full-featured seeding system for development data
- **Rate Limiting** - Flexible throttling for API endpoints
- **Feature Generators** - CLI tools to quickly scaffold new features like payments, RBAC, teams
- **Testing Setup** - Factory-based testing with pytest (no mocks needed)
- **Developer Tools** - Comprehensive Makefile, code formatting, linting with Ruff
- **Production Ready** - Docker setup, error handling, logging, S3 storage, and security configurations

## Project Structure

The project follows a modular, organized structure with each app containing its own set of directories:

```
project/
├── api/                      # Main Django project
│   ├── settings/             # Split settings (common, dev, prod)
│   ├── celery.py             # Celery configuration
│   ├── centrifugo.py         # Centrifugo JWT tokens + HTTP client
│   ├── decorators.py         # API decorators
│   ├── exceptions.py         # Custom exceptions
│   ├── permissions.py        # Permission classes
│   └── urls.py               # URL configuration
├── core/                     # Core app with user management
│   ├── admin/                # Admin interface configurations
│   ├── controllers/          # API controllers/endpoints
│   ├── management/           # Django management commands
│   ├── models/               # Database models (with base models)
│   ├── schemas/              # API schemas/serializers (Pydantic)
│   ├── services/             # Business logic layer
│   └── tests/                # Unit and integration tests
├── todos/                    # Example app with CRUD functionality
├── scripts/                  # Utility scripts
├── .cursor/                  # Cursor IDE rules
│   └── rules/
│       └── backend_guidelines.mdc
├── docker-compose.yml        # Development Docker setup
├── docker-compose.prod.yml   # Production Docker setup
├── Makefile                  # Command automation
└── pyproject.toml            # Project configuration
```

### App Structure Pattern

Each app follows this structure:

```
app_name/
├── admin/                    # Admin configurations
├── controllers/              # API endpoints (class-based)
├── management/commands/      # Management commands
├── migrations/               # Database migrations
├── models/                   # Database models
├── schemas/                  # Pydantic schemas
├── services/                 # Business logic
├── tests/
│   ├── factories/            # Test data factories
│   └── test_*.py             # Test files
└── README.md
```

## Technologies

### Core Stack

- **Python 3.13+** with type hints
- **[Django 5.2 LTS](https://docs.djangoproject.com/en/5.2/)** - Web framework (6.0 tested and ready)
- **[Django Ninja](https://django-ninja.dev/)** - Fast API framework
- **[Django Ninja Extra](https://eadwincode.github.io/django-ninja-extra/)** - Class-based controllers
- **[Django Ninja JWT](https://eadwincode.github.io/django-ninja-jwt/)** - JWT authentication
- **[PostgreSQL](https://www.postgresql.org/)** - Primary database
- **[Valkey](https://valkey.io/)** - Caching and task broker (Redis-compatible, BSD license)
- **[Celery](https://docs.celeryproject.org/)** - Background task processing (default; Huey, django-q2, django-rq also supported)
- **[Centrifugo](https://centrifugal.dev/)** - Real-time WebSocket messaging
- **[Pydantic](https://docs.pydantic.dev/)** - Data validation
- **[orjson](https://github.com/ijl/orjson)** - High-performance JSON (global renderer)

### Rust-Powered Toolchain

Performance-critical components use Rust under the hood:

- **[uv](https://docs.astral.sh/uv/)** - Package management (replaces pip/poetry)
- **[Ruff](https://docs.astral.sh/ruff/)** - Linting and formatting (replaces flake8/black/isort)
- **[ty](https://github.com/astral-sh/ty)** - Type checking (alongside mypy)
- **[pydantic-core](https://github.com/pydantic/pydantic-core)** - Validation engine (5-50x faster than v1)
- **[orjson](https://github.com/ijl/orjson)** - JSON serialization (2-10x faster than stdlib)
- **[django-vcache](https://pypi.org/project/django-vcache/)** - Cache I/O driver (default backend)

### Development Tools

- **[pytest](https://docs.pytest.org/)** - Testing framework
- **[Factory Boy](https://factoryboy.readthedocs.io/)** - Test data generation
- **[Docker](https://www.docker.com/)** - Containerization (OrbStack optimized)
- **[Django Unfold](https://unfoldadmin.com/)** - Modern admin panel

## Quick Start

### One-Command Setup (Recommended)

```bash
# Clone and setup in one go
git clone https://github.com/mattjaikaran/django-ninja-boilerplate my-api
cd my-api
make setup
```

That's it! The setup command will:

- Check your environment (Docker, Python, etc.)
- Create `.env` with generated `SECRET_KEY`
- Build Docker images
- Run migrations
- Seed sample data
- Create a superuser

Visit http://localhost:8000/api/docs for the API documentation.

### Using the CLI Tool

```bash
# Install the CLI (from cli directory)
cd cli && uv pip install -e .

# Create a new project interactively
django-ninja-matt init my-api

# Or use the short alias
dnm init my-api --type standalone --deployment railway
```

### Manual Setup

```bash
# Clone the repository
git clone https://github.com/mattjaikaran/django-ninja-boilerplate
cd django-ninja-boilerplate

# Copy environment file
cp .env.development .env

# Start the services
make up

# Run migrations and create superuser
make migrate
make create-superuser
```

### Local Development (Without Docker)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/mattjaikaran/django-ninja-boilerplate
cd django-ninja-boilerplate

# Create virtual environment and install dependencies
uv sync --dev

# Setup environment
cp .env.example .env
./scripts/generate_secret_key.sh

# Start PostgreSQL and Valkey locally, then:
make local-migrate
make local-run
```

## Available Commands

### Setup & Environment

```bash
make setup               # One-command project bootstrap
make doctor              # Validate development environment
make setup-env           # Create .env from template
```

### Docker Commands

```bash
make up                  # Start core services (db, valkey, django)
make up-celery           # Start with Celery workers
make up-realtime         # Start with Centrifugo real-time server
make up-monitoring       # Start with Flower dashboard
make up-full             # Start all services
make down                # Stop environment
make logs                # View logs
make shell               # Django shell
make migrate             # Run migrations
make test                # Run tests
make lint                # Run linting
make format              # Format code
```

### Celery Commands

```bash
make celery-worker       # Start Celery worker
make celery-beat         # Start Celery beat scheduler
make celery-flower       # Start Flower monitoring (port 5555)
make celery-inspect      # Inspect active tasks
make celery-purge        # Purge all tasks
```

### App Generation

```bash
make startapp APP=myapp                              # Create new app
make generate-feature FEATURE=payments PROVIDER=stripe   # Generate feature
make generate-data                                   # Generate sample data
```

### Database Management

```bash
# Seeding data
make seed-data               # Load comprehensive seed data
make seed-data-full          # Load with higher counts
make seed-data-clear         # Clear and reload all data

# Database dumps
make db-dump                 # Create a database dump
make db-dump-data            # Create data-only dump
make db-dump-compressed      # Create compressed dump (.sql.gz)
make db-list-dumps           # List available dumps
make db-restore FILE=docker/postgres/dumps/dump.sql  # Restore from dump
make db-clean-dumps          # Clean old dumps, keep 5 most recent
```

### Local Development

```bash
make local-run           # Run server locally
make local-test          # Run tests locally
make local-lint          # Lint locally
make local-celery        # Start Celery locally
```

Run `make help` for all available commands.

## Architecture

### Base Models

All models inherit from `AbstractBaseModel` or `SoftDeleteModel`:

```python
from core.models.base import SoftDeleteModel

class MyModel(SoftDeleteModel):
    name = models.CharField(max_length=255)

    # Automatically includes:
    # - id (UUID)
    # - created_at, updated_at
    # - created_by, updated_by
    # - is_active (soft delete)
    # - metadata (JSON field)
```

### Service Layer

Business logic goes in services:

```python
from core.services.base_service import CRUDService

class MyModelService(CRUDService[MyModel]):
    model = MyModel

    def custom_logic(self, data):
        # Your business logic here
        return self.create(data)
```

### Controllers

API endpoints use class-based controllers:

```python
from ninja_extra import api_controller, http_get, http_post
from api.decorators import handle_exceptions, log_api_call

@api_controller("/items", tags=["Items"])
class ItemController:
    @http_get("/", response=list[ItemSchema])
    @handle_exceptions()
    @log_api_call()
    def list_items(self, request):
        return Item.objects.filter(user=request.user)
```

## Authentication

The boilerplate provides multiple authentication methods:

### Traditional Auth (Email/Password)

```bash
POST /api/auth/signup      # Create account
POST /api/auth/login       # Login with email/password
POST /api/auth/logout      # Logout
GET  /api/auth/me          # Get current user
```

### Passwordless (Magic Links)

```bash
POST /api/auth/passwordless/login/request   # Request magic link
POST /api/auth/passwordless/login/verify    # Verify token
```

### OTP Authentication (Mobile/iOS Apps)

The OTP system provides 6-digit codes optimized for mobile apps:

```bash
# Request OTP code (sent via email, SMS, or push)
POST /api/auth/otp/request
{
    "email": "user@example.com",
    "purpose": "LOGIN",           # LOGIN, PASSWORD_RESET, SIGNUP_VERIFICATION, TWO_FACTOR
    "delivery_method": "EMAIL"    # EMAIL, SMS, PUSH
}

# Verify OTP and get tokens
POST /api/auth/otp/verify
{
    "email": "user@example.com",
    "code": "123456",
    "purpose": "LOGIN"
}

# Password reset via OTP
POST /api/auth/otp/password-reset/request
POST /api/auth/otp/password-reset/confirm
{
    "email": "user@example.com",
    "code": "123456",
    "new_password": "newpassword123"
}

# Two-factor authentication
POST /api/auth/otp/2fa/request    # Request 2FA code
POST /api/auth/otp/2fa/verify     # Verify 2FA code
```

**OTP Features:**

- 6-digit numeric codes (mobile-friendly)
- Configurable expiration (default: 10 minutes)
- Rate limiting to prevent brute force
- Maximum attempts per code (default: 5)
- Support for email, SMS, and push delivery
- Token-based magic links as alternative

### Rate Limiting

Apply rate limits to endpoints:

```python
from api.decorators import rate_limit

@api_controller("/items")
class ItemController:
    @rate_limit(requests_per_minute=100)
    @http_get("/")
    def list_items(self, request):
        ...

    @rate_limit(requests_per_minute=10)
    @http_post("/sensitive")
    def sensitive_action(self, request):
        ...
```

### Schemas

Use Pydantic for request/response validation:

```python
from ninja import Schema
from pydantic import Field

class CreateItemSchema(Schema):
    name: str = Field(..., min_length=1)
    description: str | None = None

class ItemSchema(Schema):
    id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True
```

## Feature Generators

Quickly scaffold complete features:

```bash
# Payments with Stripe
make generate-feature FEATURE=payments PROVIDER=stripe

# RBAC (Role-Based Access Control)
make generate-feature FEATURE=rbac PLATFORM=b2b

# Organization management
make generate-feature FEATURE=organization

# Notifications
make generate-feature FEATURE=notification
```

Available features: `payments`, `rbac`, `organization`, `team`, `subscription`, `notification`, `chat`, `file_storage`, `analytics`, `redis`, `graphql`

See [FEATURE_GENERATION.md](FEATURE_GENERATION.md) for details.

## GraphQL (Optional)

This boilerplate includes an optional GraphQL API setup using [Strawberry GraphQL](https://strawberry.rocks/). GraphQL is not included by default since REST APIs (via Django Ninja) are the primary interface.

### Setting Up GraphQL

1. **Install GraphQL dependencies:**

```bash
uv add 'strawberry-graphql[django]'
# Or install the optional group:
uv sync --extra graphql
```

2. **Generate GraphQL files for your app:**

```bash
python manage.py generate_feature graphql --app-name=core
```

This creates:

- `core/graphql/` - GraphQL package with:
  - `schema.py` - Main schema combining Query and Mutation
  - `queries.py` - Query type with example queries
  - `mutations.py` - Mutation type with example mutations
  - `types.py` - Strawberry types for models
  - `context.py` - Custom context class with user access
- `core/graphql.py` - JWT-authenticated GraphQL view

3. **Access the GraphQL playground:**

Visit http://localhost:8000/graphql/ for the interactive GraphQL playground.

### Example Query

```graphql
query {
  me {
    id
    email
    fullName
  }
  users(limit: 10) {
    id
    email
    username
  }
}
```

### Example Mutation

```graphql
mutation {
  updateUser(input: { firstName: "John", lastName: "Doe" }) {
    user {
      id
      fullName
    }
    errors {
      field
      message
    }
  }
}
```

### Authentication

GraphQL endpoints use the same JWT authentication as REST APIs. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

## Testing

This boilerplate includes comprehensive testing utilities including unit tests, E2E tests, contract tests, and load tests.

### Quick Start

```bash
make test                    # Run unit tests
make test-all                # Run all test types
make test-coverage           # Run with coverage report
```

### Unit Tests

Tests use Factory Boy for data generation (no mocks):

```bash
uv run pytest -v             # Verbose output
uv run pytest -k "test_auth" # Run specific tests
```

Example test:

```python
from core.tests.factories import UserFactory
from todos.tests.factories import TodoFactory

def test_create_todo(db, authenticated_client):
    client, user = authenticated_client
    response = client.post("/api/todos/", {"title": "Test"})
    assert response.status_code == 201
```

### E2E Tests

End-to-end tests for complete user journeys:

```bash
make test-e2e                # Run E2E tests
make generate-e2e            # Generate E2E test stubs from YAML
```

### Contract Tests

API contract tests validate responses against the OpenAPI specification using [Schemathesis](https://schemathesis.readthedocs.io/):

```bash
# Install testing dependencies
uv pip install -e ".[testing]"

# Run contract tests (requires running server)
make test-contract

# Run all contract tests including slow schema-based tests
make test-contract-full
```

Contract tests ensure:

- API responses match the documented schema
- Required fields are present
- Data types match the specification
- Error responses are properly formatted

### Load Tests

Load testing with [Locust](https://locust.io/) for performance validation:

```bash
# Interactive web UI (http://localhost:8089)
make test-load

# Quick test (10 users, 30 seconds)
make test-load-quick

# Moderate test (50 users, 2 minutes)
make test-load-moderate

# Heavy test (100 users, 5 minutes)
make test-load-heavy

# Custom test
make test-load-custom USERS=50 DURATION=2m
```

See `tests/load/README.md` for detailed load testing documentation.

### Testing Utilities

The `tests/utils/` package provides:

- **api_client.py**: Enhanced test client with auth helpers
- **assertions.py**: Custom assertions for API responses
- **factories.py**: Base factory utilities

```python
from tests.utils import APITestClient, assert_ok, assert_created

# Use the API client
client = APITestClient()
response = client.get("/api/health/")
assert_ok(response)

# Authenticated requests
from tests.utils import AuthenticatedAPIClient
auth_client = AuthenticatedAPIClient()
auth_client.login("user@example.com", "password")
response = auth_client.get("/api/auth/me")
assert_ok(response)
```

## Email Service

```python
from core.services.email import EmailService

email_service = EmailService()

# Simple email
email_service.send_simple_email(
    subject="Hello",
    message="Welcome!",
    recipient_email="user@example.com"
)

# Template email
email_service.send_templated_email(
    template_data={"html_template": "emails/welcome.html", "context": {...}},
    recipient_email="user@example.com"
)
```

## Feature Flags

The boilerplate includes a comprehensive feature flags system for:

- **Toggle features** per user, tenant, or environment
- **Gradual rollouts** with percentage-based targeting
- **A/B testing** with weighted variant distribution
- **Time-based activation** for scheduled feature releases

### Basic Usage

```python
from core.features import feature_flag_service, feature_flag

# Check if a flag is enabled
if feature_flag_service.is_enabled("new_checkout", user=request.user):
    # New checkout flow
    pass

# Use as a decorator on views
@api_controller("/checkout", tags=["Checkout"])
class CheckoutController:
    @http_get("/")
    @feature_flag("new_checkout")  # Returns 404 if flag is disabled
    def new_checkout(self, request):
        return {"message": "New checkout experience!"}
```

### Creating Feature Flags

```python
from core.features import feature_flag_service
from core.features.models import FlagType

# Simple boolean flag
feature_flag_service.create_flag(
    name="dark_mode",
    description="Enable dark mode UI",
    enabled=True,
)

# Percentage rollout (gradual release)
feature_flag_service.create_flag(
    name="new_dashboard",
    description="New dashboard redesign",
    flag_type=FlagType.PERCENTAGE.value,
    enabled=True,
    rollout_percentage=25,  # 25% of users
)

# A/B test with variants
feature_flag_service.create_flag(
    name="pricing_page",
    description="Pricing page A/B test",
    flag_type=FlagType.AB_TEST.value,
    enabled=True,
    variants={"control": 50, "variant_a": 30, "variant_b": 20},
)
```

### A/B Testing

```python
# Get variant for a user
variant = feature_flag_service.get_variant("pricing_page", user=request.user)
# Returns: "control", "variant_a", or "variant_b"

# In templates or frontend
if variant == "variant_a":
    # Show variant A pricing
    pass
```

### Middleware Integration

Add the middleware to automatically attach feature flags to requests:

```python
# settings.py
MIDDLEWARE = [
    ...
    'core.features.middleware.FeatureFlagMiddleware',
]

# In views
def my_view(request):
    if request.feature_flags.is_enabled("new_feature"):
        # Feature enabled for this user
        pass

    variant = request.feature_flags.get_variant("ab_test")
```

### API Endpoints

```bash
# Admin endpoints (authenticated)
POST   /api/admin/feature-flags/          # Create flag
GET    /api/admin/feature-flags/          # List all flags
GET    /api/admin/feature-flags/{id}      # Get flag with audit logs
PUT    /api/admin/feature-flags/{id}      # Update flag
PATCH  /api/admin/feature-flags/{id}/toggle   # Toggle flag on/off
PATCH  /api/admin/feature-flags/{id}/rollout  # Update rollout percentage
DELETE /api/admin/feature-flags/{id}      # Delete flag

# User endpoints (public)
POST   /api/feature-flags/check           # Check flag status
GET    /api/feature-flags/me              # Get all flags for current user
GET    /api/feature-flags/{name}          # Get specific flag status
```

### Advanced Features

```python
# User-specific targeting
flag.add_user(user_id)      # Enable for specific user
flag.exclude_user(user_id)  # Exclude specific user

# Environment-based flags
feature_flag_service.create_flag(
    name="debug_mode",
    environments=["development", "staging"],  # Not in production
)

# Time-based activation
from datetime import datetime, timedelta
feature_flag_service.create_flag(
    name="holiday_banner",
    starts_at=datetime(2024, 12, 20),
    ends_at=datetime(2024, 12, 26),
)

# Conditional targeting
feature_flag_service.create_flag(
    name="premium_feature",
    conditions={
        "user_attributes": {"is_staff": True},
        "context_match": {"plan": "premium"},
    },
)
```

### Admin Interface

Feature flags can be managed through the Django admin panel at `/admin/core/featureflag/` with:

- List view with filtering by status, type, and tags
- Bulk actions (enable/disable, set rollout percentages)
- Audit log tracking for all changes

## Audit Logging

The boilerplate includes a comprehensive audit logging system for compliance tracking (GDPR, SOC2, HIPAA, etc.):

### Features

- **Model Change Tracking** - Automatic logging of all model creates, updates, and deletes via Django signals
- **API Request Logging** - Middleware captures all API requests with timing and metadata
- **Authentication Events** - Login, logout, and failed login attempts are logged
- **User Activity Tracking** - Track who did what, when, and from where (IP address)
- **Compliance Ready** - Immutable audit trail with preserved user email even after deletion

### Automatic Tracking

Model changes are automatically tracked via Django signals:

```python
# Any model changes are automatically logged
user = User.objects.create(email="test@example.com", username="testuser")
# Creates audit log: CREATE User

user.first_name = "John"
user.save()
# Creates audit log: UPDATE User with changes {"first_name": {"old": "", "new": "John"}}

user.soft_delete()
# Creates audit log: SOFT_DELETE User

user.delete()
# Creates audit log: DELETE User
```

### Explicit Audit Actions

Use the decorator for custom audit logging:

```python
from core.audit import audit_action
from core.audit.models import AuditAction

@api_controller("/payments", tags=["Payments"])
class PaymentController:
    @http_post("/process")
    @audit_action(
        action=AuditAction.CUSTOM,
        action_description="Processed payment",
        model_name="Payment",
        get_object_id=lambda *args, **kwargs: kwargs.get('payment_id'),
        get_extra_data=lambda *args, **kwargs: {'amount': kwargs.get('amount')}
    )
    def process_payment(self, request, payment_id: str, amount: float):
        # Payment processing logic
        pass
```

### API Endpoints (Admin Only)

```bash
# List audit logs with filtering
GET /api/audit/?action=CREATE&model_name=User&start_date=2024-01-01

# Get specific audit log
GET /api/audit/{audit_log_id}

# Get audit statistics
GET /api/audit/stats/summary?days=30

# Get object history (all changes to a specific object)
GET /api/audit/object/User/{user_id}

# Get user activity
GET /api/audit/user/{user_email}

# Get IP address activity
GET /api/audit/ip/{ip_address}

# Get failed login attempts (security monitoring)
GET /api/audit/failed-logins?hours=24

# List available action types
GET /api/audit/actions

# List all audited models
GET /api/audit/models
```

### Configuration

```python
# settings.py

# Enable/disable audit logging
AUDIT_LOG_ENABLED = True

# Paths to audit (prefix matching)
AUDIT_LOG_PATHS = ["/api/"]

# Paths to exclude
AUDIT_LOG_EXCLUDE_PATHS = ["/api/health/", "/api/docs"]

# Log request/response bodies (disable for privacy)
AUDIT_LOG_BODY = False

# Models to exclude from tracking
AUDIT_EXCLUDED_MODELS = ["AuditLog", "Session", "ContentType"]

# Specific models to track (None = track all except excluded)
AUDIT_TRACKED_MODELS = None  # or ["User", "Todo", "Payment"]
```

### Admin Interface

Audit logs can be viewed in the Django admin at `/admin/core/auditlog/`:

- Read-only interface (audit logs cannot be modified or deleted)
- Filter by action type, user, model, success status, and date
- Search by user email, model name, IP address, request path
- Color-coded action badges for easy scanning
- Collapsible sections for detailed change data

### Action Types

| Action              | Description                           |
| ------------------- | ------------------------------------- |
| `CREATE`            | New record created                    |
| `UPDATE`            | Record updated                        |
| `DELETE`            | Record permanently deleted            |
| `SOFT_DELETE`       | Record soft deleted (is_active=False) |
| `RESTORE`           | Soft-deleted record restored          |
| `LOGIN`             | User logged in                        |
| `LOGOUT`            | User logged out                       |
| `LOGIN_FAILED`      | Failed login attempt                  |
| `PASSWORD_CHANGE`   | User changed password                 |
| `PASSWORD_RESET`    | Password reset performed              |
| `API_REQUEST`       | API endpoint accessed                 |
| `PERMISSION_CHANGE` | User permissions modified             |
| `EXPORT`            | Data exported                         |
| `IMPORT`            | Data imported                         |
| `CUSTOM`            | Custom audit action                   |

## API Key Authentication

Built-in API key auth for machine-to-machine access alongside JWT:

```python
from core.security.api_key_auth import APIKeyAuth
from ninja_jwt.authentication import JWTAuth

# Accept either JWT or API key
@api_controller("/items", tags=["Items"], auth=[JWTAuth(), APIKeyAuth()])
class ItemController:
    ...
```

Create and manage keys via the API:

```bash
# Create a key (returns raw key once)
curl -X POST /api/api-keys/ -H "Authorization: Bearer <jwt>" \
  -d '{"name": "CI Pipeline", "scopes": ["read:todos"]}'

# Use the key
curl /api/todos/ -H "X-API-Key: prefix.secret..."
```

See [docs/API_KEYS.md](docs/API_KEYS.md) for full documentation.

## Background Tasks (Pluggable Backends)

Default backend is Celery. Alternatives available via `TASK_BACKEND` env var:

| Backend              | Install               | Worker Command       |
| -------------------- | --------------------- | -------------------- |
| **Celery** (default) | Built-in              | `make celery-worker` |
| **Huey**             | `uv add huey`         | `make worker-huey`   |
| **django-q2**        | `uv add django-q2`    | `make worker-q`      |
| **django-rq**        | `uv add django-rq rq` | `make worker-rq`     |

```python
# Backend-agnostic task decorator
from api.tasks import shared_task

@shared_task
def send_welcome_email(user_id):
    ...

send_welcome_email.delay(user.id)
```

See [docs/TASK_BACKENDS.md](docs/TASK_BACKENDS.md) for comparison and setup.

### Celery (Default)

```python
from api.celery import app

@app.task
def send_welcome_email(user_id):
    # Send email async
    pass

# Call task
send_welcome_email.delay(user.id)
```

Start workers:

```bash
make celery-worker    # Start worker
make celery-beat      # Start scheduler
make celery-flower    # Monitoring at localhost:5555
```

## Real-Time Messaging (Centrifugo)

The boilerplate includes [Centrifugo](https://centrifugal.dev/) for real-time WebSocket communication. Centrifugo runs as a standalone server — Django stays WSGI and publishes events via HTTP.

### Quick Start

```bash
# Start with Centrifugo (runs on port 8800)
make up-realtime

# Admin UI at http://localhost:8800 (password: admin)
```

### How It Works

1. **Client connects** to Centrifugo via WebSocket with a JWT token
2. **Django publishes** events to Centrifugo channels via HTTP API
3. **Centrifugo delivers** messages to subscribed clients in real-time

```python
from api.centrifugo import centrifugo_client

# Publish a message to a channel
centrifugo_client.publish("chat:conversation-123", {
    "type": "chat_message",
    "message": {"content": "Hello!", "sender_id": "user-456"},
})

# Broadcast to multiple users
centrifugo_client.broadcast(
    ["notifications:user-1", "notifications:user-2"],
    {"type": "notification", "data": {"title": "New update"}},
)
```

### Token Endpoints

```bash
POST /api/realtime/connection-token     # Get WebSocket connection JWT
POST /api/realtime/subscription-token   # Get channel subscription JWT
```

### Channel Namespaces

| Namespace       | Pattern                   | Features                     |
| --------------- | ------------------------- | ---------------------------- |
| `chat`          | `chat:<conversation_id>`  | Presence, history (100 msgs) |
| `notifications` | `notifications:<user_id>` | History (50 msgs, 24h TTL)   |
| `organization`  | `organization:<org_id>`   | Presence, history (50 msgs)  |

See [docs/REALTIME.md](docs/REALTIME.md) for full setup guide, client integration examples, and production deployment.

## Task Management

The boilerplate includes a comprehensive task management system with progress tracking, periodic task scheduling, and dead letter queue handling.

### Enhanced Task Classes

Use the enhanced task base classes for automatic progress tracking:

```python
from api.celery import app
from core.tasks.base import ProgressTask, CriticalTask

@app.task(base=ProgressTask, bind=True)
def process_data(self, data_id):
    self.update_progress(0, "Starting processing...")

    # Process data in chunks
    for i, chunk in enumerate(chunks):
        process_chunk(chunk)
        self.update_progress(int((i + 1) / len(chunks) * 100), f"Processing chunk {i + 1}")

    self.update_progress(100, "Complete!")
    return {"processed": len(chunks)}

# For critical tasks that must complete (no auto-retry)
@app.task(base=CriticalTask, bind=True)
def process_payment(self, payment_id):
    # Critical operation - failures go directly to DLQ
    pass
```

### Task Status API

Monitor and manage tasks via REST API:

```bash
# Get task status and progress
GET /api/tasks/{task_id}/status

# Get real-time progress
GET /api/tasks/{task_id}/progress

# Cancel a running task
POST /api/tasks/{task_id}/revoke

# List active tasks
GET /api/tasks/active

# List recent tasks with filtering
GET /api/tasks/recent?limit=50&status=failure&task_name=process

# Get task execution statistics
GET /api/tasks/stats

# Clean up old task results
POST /api/tasks/cleanup?days=30
```

### Periodic Task Scheduling

Manage periodic tasks through the API (uses django-celery-beat):

```bash
# List all periodic tasks
GET /api/tasks/scheduler/

# Create an interval task (runs every N seconds/minutes/hours/days)
POST /api/tasks/scheduler/interval
{
    "name": "cleanup_expired_otps",
    "task": "core.tasks.cleanup_expired_otps",
    "every": 1,
    "period": "hours",
    "enabled": true,
    "description": "Clean up expired OTP codes hourly"
}

# Create a crontab task (runs on a schedule)
POST /api/tasks/scheduler/crontab
{
    "name": "daily_digest",
    "task": "core.tasks.send_daily_digest",
    "minute": "0",
    "hour": "8",
    "day_of_week": "*",
    "description": "Send daily digest at 8 AM"
}

# Toggle task enabled/disabled
POST /api/tasks/scheduler/{task_id}/toggle

# Manually trigger a periodic task
POST /api/tasks/scheduler/{task_id}/run

# Get scheduler statistics
GET /api/tasks/scheduler/stats
```

### Dead Letter Queue

Failed tasks are automatically captured in a Dead Letter Queue for inspection and retry:

```bash
# List failed tasks
GET /api/tasks/dlq/?include_resolved=false&priority=high

# Get DLQ entry details
GET /api/tasks/dlq/{entry_id}

# Retry a failed task
POST /api/tasks/dlq/{entry_id}/retry

# Retry all pending failures
POST /api/tasks/dlq/retry-all
{
    "task_name": "send_email",
    "priority": "high",
    "limit": 10
}

# Mark as resolved (won't retry)
POST /api/tasks/dlq/{entry_id}/resolve
{
    "notes": "Fixed the underlying issue"
}

# Bulk resolve entries
POST /api/tasks/dlq/resolve-bulk
{
    "entry_ids": ["uuid1", "uuid2"],
    "notes": "Known issue, resolved in v2.0"
}

# Get DLQ statistics
GET /api/tasks/dlq/stats

# Clean up old resolved entries
POST /api/tasks/dlq/cleanup?days=30
```

### TaskResult Model

Task results are persisted to the database for tracking:

```python
from core.tasks.models import TaskResult, TaskStatus

# Query task results
recent_failures = TaskResult.objects.filter(
    status=TaskStatus.FAILURE,
    created_at__gte=timezone.now() - timedelta(hours=24)
)

# Get task duration
task = TaskResult.objects.get(task_id="abc123")
print(f"Task took {task.duration} seconds")
```

### Admin Interface

Task management is available in the Django admin:

- View task execution history with progress bars
- Inspect failed tasks and errors
- Manage Dead Letter Queue entries
- Bulk retry or resolve failed tasks

## Observability

The boilerplate includes a comprehensive observability stack for production monitoring:

### Components

- **OpenTelemetry Tracing** - Distributed tracing with automatic context propagation
- **Prometheus Metrics** - Request counts, latency histograms, error rates
- **Structured JSON Logging** - Production-ready logs with trace context
- **Enhanced Health Checks** - Detailed status for all dependencies

### Quick Setup

```bash
# Install observability dependencies
uv sync --extra observability

# Start with Jaeger (tracing backend)
docker compose --profile observability up -d

# Access Jaeger UI at http://localhost:16686
# Access Prometheus metrics at http://localhost:8000/api/metrics
```

### Environment Variables

```bash
# OpenTelemetry Configuration
OTEL_SERVICE_NAME=my-api              # Service name in traces
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317  # OTLP endpoint

# Logging
USE_STRUCTURED_LOGGING=true           # Enable JSON logging (default in production)
SLOW_REQUEST_THRESHOLD_MS=1000        # Log slow requests above this threshold
```

### Tracing

Traces are automatically collected for HTTP requests. Add custom spans:

```python
from core.observability import trace_span, trace_function

# Context manager for custom spans
with trace_span("process_payment", {"order_id": order.id}):
    process_payment(order)

# Decorator for functions
@trace_function("send_notification")
def send_notification(user_id, message):
    # Automatically traced
    pass
```

### Metrics

Prometheus metrics are exposed at `/api/metrics`:

```python
from core.observability.metrics import (
    get_metrics_registry,
    timed,
)

# Register custom metrics
registry = get_metrics_registry()
my_counter = registry.register_counter(
    "my_custom_events_total",
    "Total custom events",
    ["event_type"],
)
my_counter.inc(labels={"event_type": "signup"})

# Time function execution
@timed("payment_processing_seconds")
def process_payment(amount):
    pass
```

### Structured Logging

In production, logs are output as JSON with trace context:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "User created",
  "trace_id": "abc123",
  "span_id": "def456",
  "user_id": "user-789",
  "service": "my-api"
}
```

Use the context logger:

```python
from core.observability.logging import ContextLogger

logger = ContextLogger(__name__)
logger.bind(user_id="123", request_id="abc")
logger.info("Processing order", extra={"order_id": "456"})
```

### Health Checks

Enhanced health checks with detailed status:

```bash
# Basic health check
GET /api/health/

# Detailed status (database, cache, redis)
GET /api/health/detailed

# Check specific component
GET /api/health/component/database
GET /api/health/component/redis
```

Register custom health checks:

```python
from core.observability.health import (
    register_health_check,
    HealthCheckResult,
    HealthStatus,
)

def check_payment_provider():
    # Check external service
    return HealthCheckResult(
        name="payment_provider",
        status=HealthStatus.HEALTHY,
        message="Stripe API responding",
    )

register_health_check("payment_provider", check_payment_provider)
```

### Middleware

The `ObservabilityMiddleware` automatically:

- Creates/propagates trace IDs
- Records request metrics (count, latency)
- Adds trace context to logs
- Adds `X-Trace-ID` and `X-Request-ID` headers to responses

## Deployment

### Docker Compose (Split Services)

```bash
make prod-build
make prod-up
```

### Single Container (PaaS)

For Railway, Render, Fly.io, or any PaaS:

```bash
# Build and test locally
make single-build
make single-up

# Deploy to Railway
railway up

# Deploy to Render
render blueprint apply
```

### Kubernetes

```bash
# Add Bitnami repo for dependencies
helm repo add bitnami https://charts.bitnami.com/bitnami

# Install the chart
helm install my-api ./deploy/kubernetes/helm/django-ninja-stack \
  --set postgresql.auth.password=your-db-password \
  --set image.repository=your-registry/django-ninja-stack
```

See [`deploy/`](deploy/) for detailed deployment configurations:

- `deploy/docker/` - Dockerfiles
- `deploy/centrifugo/` - Centrifugo server config
- `deploy/paas/` - Railway, Render configs
- `deploy/kubernetes/` - Helm chart

### Production Features

- Multi-stage Docker builds
- Gunicorn with workers
- Health checks at `/api/health/`
- Automatic migrations on deploy
- Secret management

## API Documentation

- **Swagger/OpenAPI**: http://localhost:8000/api/docs
- **Admin Panel**: http://localhost:8000/admin

### OpenAPI Tools

Export your API specification and generate client SDKs:

```bash
# Export OpenAPI specification
make openapi

# Generate TypeScript and Python SDK clients
make sdk

# Export Postman collection
make postman

# Export Insomnia collection
make insomnia

# Generate everything (spec, SDKs, collections)
make openapi-all

# Validate OpenAPI specification
make openapi-validate
```

#### SDK Generation

Generate typed client SDKs from your API:

```bash
# Generate all SDKs
python manage.py export_openapi --sdk

# TypeScript SDK
python manage.py export_openapi --sdk-typescript

# Python SDK
python manage.py export_openapi --sdk-python
```

#### API Changelog

Compare API versions to generate changelogs:

```bash
# Generate changelog between two API versions
make changelog OLD=docs/openapi/openapi-v1.json NEW=docs/openapi/openapi-v2.json

# Or use the script directly
python scripts/openapi/generate_changelog.py old.json new.json -o CHANGELOG.md
```

See [docs/openapi/README.md](docs/openapi/README.md) for detailed documentation.

## Contributing

1. Clone the repository
2. Install dependencies: `uv sync`
3. Create a feature branch: `git checkout -b feature/your-feature-name`
4. Make your changes: `git add . && git commit -m "Add detailed description of your changes"`
5. Push your feature branch: `git push origin feature/your-feature-name`
6. Create a pull request: `gh pr create`
7. Wait for review and approval
8. Merge your pull request
9. Delete your feature branch: `git branch -D feature/your-feature-name`
