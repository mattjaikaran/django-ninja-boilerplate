# Django Ninja Boilerplate

A comprehensive, production-ready Django boilerplate using Django Ninja for building modern APIs. This enhanced version includes advanced authentication (magic links + traditional), monitoring, caching, health checks, email services, and rapid feature generators for scalable API development.

## ✨ Key Enhancements

🚀 **Complete Authentication System** - Traditional login/register + passwordless magic links  
📧 **Advanced Email Service** - Template-based emails with multiple backends  
⚡ **Comprehensive Caching** - Multi-layer caching with decorators  
📊 **Monitoring & Metrics** - Performance tracking and system health monitoring  
🏥 **Health Check System** - Kubernetes-ready health endpoints  
🛠️ **Feature Generators** - Rapid scaffolding for new API endpoints  
🔧 **Advanced Utilities** - Validation, formatting, HTTP helpers  
🎯 **Production Ready** - Error handling, logging, security features

👉 **[See complete feature documentation →](FEATURES.md)**

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

- Python 3.11+
- [Django 5.2](https://docs.djangoproject.com/en/5.2/)
- [Django Ninja](https://django-ninja.dev/)
- [Django Ninja Extra](https://eadwincode.github.io/django-ninja-extra/) a collection of extra features for Django Ninja
- [Django Ninja JWT](https://eadwincode.github.io/django-ninja-jwt/)
  - [Django Simple JWT](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/) abstraction for Django Ninja
- [Postgres](https://www.postgresql.org/docs/) database
- [Pydantic](https://docs.pydantic.dev/latest/)
- [Django Unfold Admin](https://unfoldadmin.com/)
  - [Unfold Docs](https://github.com/unfoldadmin/django-unfold)
- [uv](https://docs.astral.sh/uv/) for fast Python package management
- Docker & Docker Compose
- pytest for testing
- Gunicorn for production serving

#### Dev Tools & Features

- Makefile to run commands
- PyTest for comprehensive testing
- [uv](https://docs.astral.sh/uv/) for fast package management
- Custom Start App command to create a new app
  - with extended functionality for Django Ninja, Django Ninja Extra, and Django Unfold
  - `make startapp <app_name>`
- [Faker](https://faker.readthedocs.io/en/master/) for generating fake data.
  - See `@/core/management/commands/generate_core_data.py` for more information
- [Swagger](https://swagger.io/) for API documentation
  - [Localhost Docs](http://localhost:8000/api/docs)
- [Debug Toolbar](https://django-debug-toolbar.readthedocs.io/en/latest) for debugging
- [Django Environ](https://django-environ.readthedocs.io/en/latest/) for managing environment variables
- Linting & Formatting
  - [Ruff](https://docs.astral.sh/ruff/) - Fast Python linter and formatter (replaces Black, isort, Flake8)
  - Configuration in `pyproject.toml`
  - Run with `make lint` or `make format`
  - Legacy script available at `@/scripts/lint.sh`

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
touch .env

# Setup database and create superuser
make db-setup

# Generate secret key
./scripts/generate_secret_key.sh

# Run the development server
make runserver
```

### Traditional Setup (Legacy)

```bash
git clone https://github.com/mattjaikaran/django-ninja-boilerplate
cd django-ninja-boilerplate

# Create and activate virtual environment
python3 -m venv env
source env/bin/activate

# Install dependencies (Note: requirements.txt is deprecated)
pip3 install -e .

# Create environment file and update with your settings
touch .env

# Apply migrations and create superuser
python3 manage.py migrate
python3 manage.py create_superuser

# Generate secret key
./scripts/generate_secret_key.sh

# Run the development server
python3 manage.py runserver
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

This runs `uv add <library-name>` and updates pyproject.toml

```bash
$ make install <library-name>
# example
# make install django-ninja-jwt
```

### Sync dependencies

Install all dependencies from pyproject.toml

```bash
$ make sync      # Production dependencies only
$ make sync-dev  # Include development dependencies
```

### Drop DB, Create DB, Migrate, Create Superuser via db-setup script

```bash
$ make db-setup
```

## Why Django Ninja?

- [Django Ninja Docs](https://django-ninja.dev/)

Django Ninja is a newer framework that can run on Django 5.0, built in OpenAPI/Swagger/ReDoc, has async support, and uses Pydantic. It almost has a FastAPI vibe with some Django features.

By following this approach, the front-end can easily consume the JSON data from these endpoints. The API will be self-documenting and you can view the OpenAPI (Swagger) documentation by navigating to `/api/docs` in your browser.

### Why Django Ninja Extra?

- [Django Ninja Extra Docs](https://eadwincode.github.io/django-ninja-extra/)

When building Django apps, I am mostly familiar with a class-based views architecture and ninja-extra makes the transition from DRF to ninja a little easier. There are permissions and dependency injection included.

### Django Ninja Serialization

- Django Ninja uses Pydantic models (Schemas) for serialization, not Django serializers like in DRF.
- The response parameter in the route decorator specifies the expected response format.
- Use from_orm() to convert Django ORM objects to Pydantic models.
- Django Ninja automatically handles the conversion to JSON in the HTTP response.

## Admin Panel

- [Django Unfold Docs](https://github.com/unfoldadmin/django-unfold)

Django Unfold has one of the cleaniest designs for Django admin panels. Pretty easy to get set up and there is now support for certain libraries that broke the design (ie - django-import-export)

## Production Deployment

1. Update `.env` with production settings
2. Build and run with Docker:

```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

## Testing (Factory-Based, No Mocks)

This boilerplate uses factory-based testing with Factory Boy for creating test data, eliminating the need for mocks and providing more realistic test scenarios.

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test file
uv run pytest path/to/test_file.py

# Run specific test class
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

- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`

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

## Database

```bash
$ psql my_db # enter shell
$ createdb --username=USERNAME my_db # create db
$ dropdb my_db # drop db
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
