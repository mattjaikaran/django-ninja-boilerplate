# create-django-ninja-stack

CLI tool for scaffolding Django Ninja Stack projects with modern tooling and best practices.

## Installation

```bash
# Using pipx (recommended)
pipx install create-django-ninja-stack

# Using pip
pip install create-django-ninja-stack

# Using uv
uv tool install create-django-ninja-stack
```

## Quick Start

```bash
# Create a new project interactively
create-django-ninja-stack my-app

# Or use the short alias
cdns my-app
```

## Features

- Interactive project scaffolding with smart defaults
- Multiple project types:
  - **Standalone API** - Django Ninja backend only
  - **Fullstack Monorepo** - Django backend + React-Vite frontend
- Feature selection:
  - Authentication methods (JWT, OAuth, OTP)
  - Background tasks (Celery)
  - Caching (Redis)
  - And more...
- Deployment configurations:
  - Docker Compose (development & production)
  - Railway
  - Render
  - Kubernetes (Helm charts)
- Professional DX tooling:
  - One-command setup (`make setup`)
  - Environment doctor (`make doctor`)
  - VSCode configurations
  - CI/CD workflows

## Usage

### Create a New Project

```bash
# Interactive mode (recommended)
create-django-ninja-stack my-project

# With options
create-django-ninja-stack my-project --type standalone --no-celery
create-django-ninja-stack my-project --type monorepo --frontend react-vite
```

### Project Management Commands

After creating a project, navigate to it and use:

```bash
cd my-project

# Bootstrap the development environment
make setup

# Validate your environment
make doctor

# Start development services
make up

# Run tests
make test
```

### Available Options

```bash
create-django-ninja-stack --help
```

| Option | Description | Default |
|--------|-------------|---------|
| `--type` | Project type: `standalone` or `monorepo` | Interactive |
| `--frontend` | Frontend framework (monorepo only): `react-vite` | `react-vite` |
| `--no-celery` | Skip Celery setup | False |
| `--no-redis` | Skip Redis setup | False |
| `--deployment` | Deployment target: `docker`, `railway`, `render`, `k8s` | `docker` |

## Project Types

### Standalone API

A Django Ninja API-only project, perfect for:
- Backend services
- Microservices
- APIs consumed by mobile apps or external frontends

```
my-app/
├── api/              # Django project
├── core/             # Core app (users, auth)
├── docker/           # Docker configs
├── scripts/          # Setup scripts
├── docker-compose.yml
├── Makefile
└── ...
```

### Fullstack Monorepo

A complete fullstack project with Django backend and React frontend:

```
my-app/
├── backend/          # Django Ninja API
├── frontend/         # React Vite SPA
├── deploy/           # Deployment configs
├── docker-compose.yml
├── Makefile
└── ...
```

## Development

```bash
# Clone the repository
git clone https://github.com/mattjaikaran/django-ninja-boilerplate.git
cd django-ninja-boilerplate/cli

# Install in development mode
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
```

## License

MIT License - see [LICENSE](LICENSE) for details.
