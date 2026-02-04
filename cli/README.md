# django-ninja-matt

CLI tool for scaffolding Django Ninja Boilerplate projects with modern tooling and best practices.

## Installation

```bash
# Install from the cli directory
cd cli
uv pip install -e .

# Or install globally with pipx (when published)
pipx install django-ninja-matt
```

## Quick Start

```bash
# Create a new project interactively
django-ninja-matt init my-app

# Or use the short alias
dnm init my-app
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
django-ninja-matt init my-project

# With options
dnm init my-project --type standalone --no-celery
dnm init my-project --type monorepo --deployment railway
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

### Available Commands

```bash
django-ninja-matt --help
dnm --help
```

| Command | Description |
|---------|-------------|
| `dnm init <name>` | Create a new project |
| `dnm doctor` | Validate development environment |
| `dnm setup` | Bootstrap current project |

### Init Options

| Option | Description | Default |
|--------|-------------|---------|
| `--type` | Project type: `standalone` or `monorepo` | Interactive |
| `--deployment` | Deployment target: `docker`, `railway`, `render`, `k8s` | `docker` |
| `--no-celery` | Skip Celery setup | False |
| `--no-redis` | Skip Redis setup | False |
| `--no-git` | Skip Git initialization | False |
| `--yes, -y` | Skip confirmation prompts | False |

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
