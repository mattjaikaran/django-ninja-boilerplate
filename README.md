# Django Ninja Boilerplate

A production-ready Django boilerplate built with **Django Ninja Extra** for creating modern REST APIs using **class-based controllers** (not function views). This project provides everything you need to quickly build scalable APIs with authentication, caching, monitoring, background tasks, and automated feature generation.

> **Architecture Note:** This boilerplate uses [Django Ninja Extra](https://eadwincode.github.io/django-ninja-extra/) which extends Django Ninja with class-based API controllers, dependency injection, and permissions. Instead of function-based views, you write clean controller classes with decorators like `@api_controller` and `@http_get`.

[![CI](https://github.com/mattjaikaran/django-ninja-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/mattjaikaran/django-ninja-boilerplate/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Django 6.0](https://img.shields.io/badge/django-6.0-green.svg)](https://docs.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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
- **Caching Layer** - Redis integration with decorators for easy caching
- **Background Tasks** - Celery integration with Redis broker and Flower monitoring
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

- **Python 3.12+** with type hints
- **[Django 6.0](https://docs.djangoproject.com/en/6.0/)** - Web framework
- **[Django Ninja](https://django-ninja.dev/)** - Fast API framework
- **[Django Ninja Extra](https://eadwincode.github.io/django-ninja-extra/)** - Class-based controllers
- **[Django Ninja JWT](https://eadwincode.github.io/django-ninja-jwt/)** - JWT authentication
- **[PostgreSQL](https://www.postgresql.org/)** - Primary database
- **[Redis](https://redis.io/)** - Caching and task queue
- **[Celery](https://docs.celeryproject.org/)** - Background task processing
- **[Pydantic](https://docs.pydantic.dev/)** - Data validation

### Development Tools

- **[uv](https://docs.astral.sh/uv/)** - Fast Python package management
- **[Ruff](https://docs.astral.sh/ruff/)** - Linting and formatting
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
cp env.example .env
./scripts/generate_secret_key.sh

# Start PostgreSQL and Redis locally, then:
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
make up                  # Start core services (db, redis, django)
make up-celery           # Start with Celery workers
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
from api.throttling import rate_limit, auth_rate_limit

@api_controller("/items")
class ItemController:
    @rate_limit(rate=100, period=60)  # 100 req/min
    @http_get("/")
    def list_items(self, request):
        ...

    @auth_rate_limit  # 10 req/min for auth endpoints
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

## Authentication

### JWT Authentication

```python
# Login
POST /api/auth/login
{
    "email": "user@example.com",
    "password": "password"
}

# Returns
{
    "token": "eyJ...",
    "refresh": "eyJ...",
    "user": {...}
}
```

### Passwordless (Magic Link)

```python
# Request magic link
POST /api/auth/passwordless/login/request
{"email": "user@example.com"}

# Verify token
POST /api/auth/passwordless/login/verify
{"token": "your-magic-link-token"}
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

## Background Tasks (Celery)

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
