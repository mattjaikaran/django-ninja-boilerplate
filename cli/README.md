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
  - One-command setup (`just setup`)
  - Environment doctor (`just doctor`)
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
just setup

# Validate your environment
just doctor

# Start development services
just up

# Run tests
just test
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
| `dnm decide route "<task>"` | Pick a model tier for a coding task |
| `dnm decide triage --commit <rev>` | Classify a commit and choose its review depth |
| `dnm decide gate "<action>" --environment <env>` | Check whether an action needs approval |
| `dnm decide generator "<request>" --app-name <name>` | Pick a `generate_feature` generator |
| `dnm decide eval --provider <p> --output <file>` | Evaluate a provider on the decision benchmark |
| `dnm decide compare <reports...>` | Compare saved eval reports on the test split |

`dnm decide` runs `uv run python manage.py ...` in the current project, so
run it from the project root. It uses the project's `SYSTEMONE_PROVIDER` and
`DECISION_THRESHOLDS_FILE`. It exits with status 3 when the decision is
`escalate` or `ask_human`, so a hook or script can stop and hand over.

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
├── justfile
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
