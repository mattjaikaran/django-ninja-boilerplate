# Django Ninja Boilerplate

A production-ready Django boilerplate built with Django Ninja for creating modern REST APIs. This project provides everything you need to quickly build scalable APIs with authentication, caching, monitoring, and automated feature generation.

## What's Included

This boilerplate gives you a solid foundation with:

- **Authentication System** - JWT-based auth with both traditional login and passwordless magic links
- **Email Service** - Template-based email system with multiple backend support
- **Caching Layer** - Redis integration with decorators for easy caching
- **Monitoring Tools** - Performance tracking and health check endpoints
- **Feature Generators** - CLI tools to quickly scaffold new features like payments, RBAC, teams
- **Testing Setup** - Factory-based testing with pytest (no mocks needed)
- **Developer Tools** - Comprehensive Makefile, code formatting, linting with Ruff
- **Production Ready** - Docker setup, error handling, logging, and security configurations

## Project Structure

The project follows a modular, organized structure with each app containing its own set of directories for different functionalities:

```
project/
├── api/                  # Main Django project with settings
├── core/                 # Core app with user management
│   ├── admin/            # Admin interface configurations
│   ├── controllers/      # API controllers/endpoints
│   ├── management/       # Django management commands
│   ├── migrations/       # Database migrations
│   ├── models/           # Database models
│   ├── schemas/          # API schemas/serializers
│   └── tests/            # Unit and integration tests
├── todos/                # Example app with CRUD functionality
│   ├── admin/            # Admin interface configurations
│   ├── controllers/      # API controllers/endpoints
│   ├── management/       # Django management commands
│   ├── migrations/       # Database migrations
│   ├── models/           # Database models
│   ├── schemas/          # API schemas/serializers
│   └── tests/            # Unit and integration tests
└── scripts/              # Utility scripts
```

Each app follows a robust structure that separates concerns:

- **models/**: Contains database models in separate files
- **controllers/**: Contains API endpoints using Django Ninja Extra's api_controller
- **schemas/**: Pydantic models for request/response validation
- **admin/**: Django admin configurations
- **tests/**: Unit and integration tests
- **management/commands/**: Custom management commands

## Technologies

- Python 3.12+
- [Django 5.2](https://docs.djangoproject.com/en/5.2/)
- [Django Ninja](https://django-ninja.dev/)
- [Django Ninja Extra](https://eadwincode.github.io/django-ninja-extra/) - collection of extra features for Django Ninja
- [Django Ninja JWT](https://eadwincode.github.io/django-ninja-jwt/)
  - [Django Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/) abstraction for Django Ninja
- [PostgreSQL](https://www.postgresql.org/docs/) database
- [Pydantic](https://docs.pydantic.dev/latest/)
- [Django Unfold Admin](https://unfoldadmin.com/)
  - [Unfold Docs](https://github.com/unfoldadmin/django-unfold)
- [uv](https://docs.astral.sh/uv/) for fast Python package management
- Docker & Docker Compose
- pytest for testing
- Gunicorn for production serving

#### Development Tools & Features

- Makefile for command automation
- PyTest for comprehensive testing
- [uv](https://docs.astral.sh/uv/) for fast package management
- Custom Start App command to create new apps
  - Extended functionality for Django Ninja, Django Ninja Extra, and Django Unfold
  - `make startapp <app_name>`
- [Faker](https://faker.readthedocs.io/en/master/) for generating fake data
  - See `core/management/commands/generate_core_data.py` for more information
- [Swagger](https://swagger.io/) for API documentation
  - [Localhost Docs](http://localhost:8000/api/docs)
- [Debug Toolbar](https://django-debug-toolbar.readthedocs.io/en/latest) for debugging
- [Django Environ](https://django-environ.readthedocs.io/en/latest/) for managing environment variables
- Linting & Formatting
  - [Ruff](https://docs.astral.sh/ruff/) - Fast Python linter and formatter (replaces Black, isort, Flake8)
  - Configuration in `pyproject.toml`
  - Run with `make lint` or `make format`

## Quick Start with Docker (Optimized for OrbStack)

```bash
# Clone the repository
git clone https://github.com/mattjaikaran/django-ninja-boilerplate
cd django-ninja-boilerplate

# Automated setup (recommended)
./scripts/setup.sh

# Or manual setup:
# Create environment file
cp env.example .env
# Edit .env with your settings

# Start the services
make up

# Generate secret key
./scripts/generate_secret_key.sh --update-env
```

Visit http://localhost:8000/api/docs for the API documentation.

### Available Make Commands

```bash
make help              # Show all available commands
make up                # Start development environment
make down              # Stop development environment
make logs              # View all service logs
make shell             # Open Django shell
make migrate           # Run database migrations
make test              # Run tests with factory-based data
make lint              # Run code linting
make format            # Format code
make db-backup         # Backup database
make db-restore        # Restore database
```

## Local Development Setup

### With uv (Recommended)

```bash
git clone https://github.com/mattjaikaran/django-ninja-boilerplate
cd django-ninja-boilerplate

# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync --dev

# Create environment file and update with your settings
cp env.example .env

# Setup database and create superuser
make db-setup

# Generate secret key
./scripts/generate_secret_key.sh

# Run the development server
make runserver
```

### Alternative Setup (Without Docker)

```bash
git clone https://github.com/mattjaikaran/django-ninja-boilerplate
cd django-ninja-boilerplate

# Create and activate virtual environment
python3 -m venv env
source env/bin/activate

# Install dependencies with uv
uv sync --dev

# Create environment file and update with your settings
cp env.example .env

# Apply migrations and create superuser
uv run python manage.py migrate
uv run python manage.py create_superuser

# Generate secret key
./scripts/generate_secret_key.sh

# Run the development server
uv run python manage.py runserver
```

## Commands

### Start a new Django App

```bash
# start a new django app with extended functionality
# for Django Ninja, Django Ninja Extra, and Django Unfold.
$ make startapp <app_name>
```

### Run Server

```bash
$ make runserver
```

### Install a library

Add new dependencies using uv:

```bash
# Add production dependency
make add PACKAGE=django-ninja-jwt

# Add development dependency
make add-dev PACKAGE=pytest-django
```

### Sync dependencies

Install all dependencies from pyproject.toml:

```bash
make sync      # Production dependencies only
make sync-dev  # Include development dependencies
```

### Drop DB, Create DB, Migrate, Create Superuser via db-setup script

```bash
$ make db-setup
```

## Why Django Ninja?

Django Ninja brings modern API development to Django with:

- **Modern Python** - Full type hints and Pydantic integration
- **Automatic Documentation** - Built-in OpenAPI/Swagger docs at `/api/docs`
- **FastAPI-like DX** - Familiar syntax if you've used FastAPI
- **Django Integration** - Works seamlessly with Django's ORM, auth, and ecosystem
- **Async Support** - Handle async views and database operations
- **Performance** - Fast request/response cycle with automatic serialization

### Django Ninja Extra

[Django Ninja Extra](https://eadwincode.github.io/django-ninja-extra/) adds class-based controllers and additional features:

- **Class-based Controllers** - Organize related endpoints together
- **Permissions & Auth** - Built-in authentication and permission decorators
- **Dependency Injection** - Clean separation of concerns
- **Advanced Routing** - More flexible URL patterns

### API Serialization

Unlike Django REST Framework, Django Ninja uses:

- **Pydantic Models** for request/response schemas instead of Django serializers
- **Automatic Validation** - Request data is validated against Pydantic schemas
- **Type Safety** - Full type checking throughout your API
- **Auto Documentation** - Schemas automatically generate OpenAPI docs

## Admin Interface

The project uses [Django Unfold](https://github.com/unfoldadmin/django-unfold) for a modern admin interface that:

- Provides a clean, contemporary design
- Supports dark/light themes
- Works with existing Django admin customizations
- Integrates well with third-party packages

## Production Deployment

1. Update `.env` with production settings
2. Build and run with Docker:

```bash
make prod-build
make prod-up
```

## Testing (Factory-Based, No Mocks)

This boilerplate uses factory-based testing with Factory Boy for creating test data, eliminating the need for mocks and providing more realistic test scenarios.

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test file
make test path/to/test_file.py

# Run specific test class (using uv directly)
uv run pytest path/to/test_file.py::TestClassName

# Run with verbose output
uv run pytest -v
```

### Test Structure

- **Factories**: Located in `*/tests/factories/` directories
- **Factory Boy**: Used for creating realistic test data
- **No Mocks**: Tests use actual database operations with factory-generated data
- **Pytest**: Modern testing framework with extensive plugin support
- **Coverage**: Integrated coverage reporting

Example factory usage:

```python
from core.tests.factories import UserFactory, TodoFactory

# Create a user with factory
user = UserFactory()

# Create a todo with custom data
todo = TodoFactory(title="Custom Title", created_by=user)
```

## API Documentation

- ReDoc: `/api/docs`

## Features

### Core Features

- JWT Authentication with Django Ninja JWT
- PostgreSQL Database (with Redis for caching)
- Docker & Docker Compose setup optimized for OrbStack
- Factory-based testing with Factory Boy (no mocks)
- Fast package management with uv
- Code linting and formatting with Ruff
- Production-ready with Gunicorn + Nginx
- Environment-based settings with django-environ
- Custom user model with OneTimePassword for passwordless auth
- Modern admin panel with Django Unfold
- API throttling, pagination, and CORS configuration
- Debug toolbar for development
- Modern Python tooling (Django 5.2, pyproject.toml)

### Developer Experience (DX)

- **Comprehensive Makefile**: 50+ commands for common tasks
- **Setup Scripts**: Automated environment setup with `./scripts/setup.sh`
- **Database Management**: `./scripts/db_setup.sh` for database operations
- **Code Quality**: `./scripts/lint.sh` for linting and formatting
- **Secret Generation**: `./scripts/generate_secret_key.sh` for secure keys
- **Hot Reloading**: Docker setup with volume mounts for development
- **Health Checks**: Built-in health check endpoints
- **OrbStack Optimization**: Docker setup optimized for Apple Silicon

### Docker & Production

- **Multi-stage Dockerfile**: Optimized for production with non-root user
- **Docker Compose**: Separate configs for development and production
- **Nginx**: Reverse proxy with SSL/TLS support
- **Health Checks**: Service health monitoring
- **Volume Management**: Persistent data storage
- **Log Management**: Centralized logging setup

## Database Management

```bash
# Database operations through Docker
make db-shell     # Enter PostgreSQL shell
make db-backup    # Backup database
make db-restore FILE=backup.sql  # Restore from backup

# Direct PostgreSQL commands (if running locally)
psql my_db # enter shell
createdb --username=USERNAME my_db # create db
dropdb my_db # drop db
```
