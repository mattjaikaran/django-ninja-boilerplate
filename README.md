# Django Ninja Stack

A production-ready Django boilerplate built with Django Ninja for creating modern REST APIs. This project provides everything you need to quickly build scalable APIs with authentication, caching, monitoring, background tasks, and automated feature generation.

[![CI](https://github.com/mattjaikaran/django-ninja-boilerplate/actions/workflows/ci.yml/badge.svg)](https://github.com/mattjaikaran/django-ninja-boilerplate/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-green.svg)](https://docs.djangoproject.com/)
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
- **[Django 5.2](https://docs.djangoproject.com/en/5.2/)** - Web framework
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
# Install the CLI
pipx install create-django-ninja-stack

# Create a new project interactively
create-django-ninja-stack my-api

# Or with options
create-django-ninja-stack my-api --type standalone --deployment railway
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

Available features: `payments`, `rbac`, `organization`, `team`, `subscription`, `notification`, `chat`, `file_storage`, `analytics`, `redis`

See [FEATURE_GENERATION.md](FEATURE_GENERATION.md) for details.

## Testing

Tests use Factory Boy for data generation (no mocks):

```bash
make test                    # Run all tests
make test-coverage           # Run with coverage report
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
