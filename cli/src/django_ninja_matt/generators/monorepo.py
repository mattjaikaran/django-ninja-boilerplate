"""Monorepo (fullstack) project generator."""

from django_ninja_matt.config import DEFAULT_BRANCH, REPO_URLS, ProjectConfig
from django_ninja_matt.generators.base import BaseGenerator
from django_ninja_matt.utils.console import (
    create_progress,
    print_error,
    print_success,
)
from django_ninja_matt.utils.git import clone_repo, git_available, remove_git_history
from django_ninja_matt.utils.project_env import load_env_secrets


class MonorepoGenerator(BaseGenerator):
    """Generator for fullstack monorepo projects."""

    def run(self) -> bool:
        """Generate a fullstack monorepo project."""
        with create_progress() as progress:
            task = progress.add_task("Creating monorepo...", total=7)

            # Step 1: Create root directory
            progress.update(task, description="Creating directory structure...")
            if not self.create_directory():
                return False
            progress.advance(task)

            # Step 2: Clone backend
            progress.update(task, description="Cloning backend...")
            if not self._clone_backend():
                return False
            progress.advance(task)

            # Step 3: Clone frontend
            progress.update(task, description="Cloning frontend...")
            if not self._clone_frontend():
                return False
            progress.advance(task)

            # Step 4: Create root files
            progress.update(task, description="Creating root configuration...")
            self._create_root_files()
            progress.advance(task)

            # Step 5: Customize projects
            progress.update(task, description="Customizing projects...")
            self._customize_projects()
            progress.advance(task)

            # Step 6: Clean up
            progress.update(task, description="Cleaning up...")
            self._cleanup()
            progress.advance(task)

            # Step 7: Initialize git
            progress.update(task, description="Initializing git...")
            self.init_git_repository()
            progress.advance(task)

        return True

    def _clone_backend(self) -> bool:
        """Clone the backend repository."""
        if not git_available():
            print_error("Git is required to create projects")
            return False

        backend_path = self.config.path / "backend"
        success = clone_repo(
            url=REPO_URLS["backend"],
            destination=backend_path,
            branch=DEFAULT_BRANCH,
        )

        if success:
            # Remove .git from backend
            remove_git_history(backend_path)

        return success

    def _clone_frontend(self) -> bool:
        """Clone the frontend repository."""
        frontend_path = self.config.path / "frontend"
        success = clone_repo(
            url=REPO_URLS["frontend"],
            destination=frontend_path,
            branch=DEFAULT_BRANCH,
        )

        if success:
            # Remove .git from frontend
            remove_git_history(frontend_path)

        return success

    def _create_root_files(self) -> None:
        """Create root-level configuration files."""
        # Root Makefile
        self._create_root_makefile()

        # Root docker-compose.yml
        self._create_root_docker_compose()

        # Root README
        self._create_root_readme()

        # Root .env files
        self._create_root_env()

        # VERSION and CHANGELOG
        (self.config.path / "VERSION").write_text("0.1.0\n")

        print_success("Created root configuration files")

    def _create_root_makefile(self) -> None:
        """Create root Makefile for orchestrating both projects."""
        content = f"""# {self.config.display_name} - Monorepo Makefile
# Orchestrates both backend and frontend services.
# The backend ships a justfile; these targets delegate to it.

.PHONY: help setup up down logs test lint

# Default target
help: ## Show this help
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {{FS = ":.*?## "}}; {{printf "\\033[36m%-20s\\033[0m %s\\n", $$1, $$2}}'

# ===========================================
# Full Stack Commands
# ===========================================

setup: ## Bootstrap the entire development environment
	@echo "Setting up {self.config.display_name}..."
	@cd backend && just setup

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## View logs for all services
	docker compose logs -f

restart: ## Restart all services
	docker compose restart

# ===========================================
# Backend Commands
# ===========================================

backend-setup: ## Setup backend only
	@cd backend && just setup

backend-up: ## Start backend services
	@cd backend && just up

backend-down: ## Stop backend services
	@cd backend && just down

backend-logs: ## View backend logs
	@cd backend && just logs

backend-shell: ## Open Django shell
	@cd backend && just shell

backend-test: ## Run backend tests
	@cd backend && just test

backend-lint: ## Lint backend code
	@cd backend && just lint

backend-migrate: ## Run backend migrations
	@cd backend && just migrate

# ===========================================
# Frontend Commands
# ===========================================

frontend-setup: ## Setup frontend only
	@cd frontend && bun install

frontend-dev: ## Start frontend dev server
	@cd frontend && bun run dev

frontend-build: ## Build frontend for production
	@cd frontend && bun run build

frontend-test: ## Run frontend tests
	@cd frontend && bun run test

frontend-lint: ## Lint frontend code
	@cd frontend && bun run lint

# ===========================================
# Development
# ===========================================

doctor: ## Check development environment
	@cd backend && just doctor

test: backend-test frontend-test ## Run all tests

lint: backend-lint frontend-lint ## Lint all code

# ===========================================
# Production
# ===========================================

prod-build: ## Build production images
	docker compose -f docker-compose.yml --profile prod build

prod-up: ## Start production environment
	docker compose -f docker-compose.yml --profile prod up -d

prod-down: ## Stop production environment
	docker compose -f docker-compose.yml --profile prod down
"""
        (self.config.path / "Makefile").write_text(content)

    def _create_root_docker_compose(self) -> None:
        """Create root docker-compose.yml."""
        content = f"""# {self.config.display_name} - Docker Compose
# Development environment with backend and frontend

services:
  # PostgreSQL Database
  db:
    image: postgres:17-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=${{DB_NAME:-{self.config.python_package_name}_db}}
      - POSTGRES_USER=${{DB_USER:-postgres}}
      - POSTGRES_PASSWORD=${{DB_PASSWORD:-postgres}}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Redis
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Django Backend
  backend:
    build: ./backend
    command: >
      sh -c "python manage.py migrate &&
             python manage.py runserver 0.0.0.0:8000"
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      - DEBUG=1
      - DB_HOST=db
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  # React Frontend (development)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000/api
    depends_on:
      - backend

volumes:
  postgres_data:
  redis_data:
"""
        (self.config.path / "docker-compose.yml").write_text(content)

    def _create_root_readme(self) -> None:
        """Create root README.md."""
        content = f"""# {self.config.display_name}

{self.config.description or "A fullstack application with Django Ninja backend and React frontend."}

## Project Structure

```
{self.config.name}/
├── backend/          # Django Ninja API
├── frontend/         # React Vite SPA
├── docker-compose.yml
├── Makefile
└── README.md
```

## Quick Start

```bash
# Bootstrap everything
just setup

# Or start services individually
make backend-up    # Start backend services
make frontend-dev  # Start frontend dev server
```

## Development

### Backend (Django)

```bash
cd backend
just setup         # Initial setup
just up            # Start services
just test          # Run tests
just shell         # Django shell
```

- API Docs: http://localhost:8000/api/docs
- Admin: http://localhost:8000/admin

### Frontend (React)

```bash
cd frontend
bun install        # Install dependencies
bun run dev        # Start dev server
bun run test       # Run tests
bun run build      # Production build
```

- Dev server: http://localhost:3000

## Available Commands

Run `just help` to see all available commands.

| Command | Description |
|---------|-------------|
| `just setup` | Bootstrap entire project |
| `just up` | Start all services |
| `just down` | Stop all services |
| `just test` | Run all tests |
| `just lint` | Lint all code |

---

Created with [Django Ninja Boilerplate](https://github.com/mattjaikaran/django-ninja-boilerplate)
"""
        (self.config.path / "README.md").write_text(content)

    def _create_root_env(self) -> None:
        """Create backend/.env with generated secrets, then the root env files.

        The root docker-compose.yml reads DB_* from the root .env; Django reads
        backend/.env. The root file copies the backend's generated database
        password, so both sides agree.
        """
        backend = self.config.path / "backend"
        db_name = f"{self.config.python_package_name}_db"
        self.create_env_file(backend, {"DB_NAME": db_name})

        def render(db_password: str) -> str:
            return f"""# {self.config.display_name} - Environment Variables
# The root docker-compose.yml reads this file. Django reads backend/.env,
# which holds the same DB_* values and the other generated secrets.

# Database
DB_NAME={db_name}
DB_USER=postgres
DB_PASSWORD={db_password}
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# Frontend
VITE_API_URL=http://localhost:8000/api
"""

        (self.config.path / ".env.example").write_text(render(""))
        backend_env = backend / ".env"
        secrets_module = load_env_secrets(backend)
        db_password = secrets_module.read_env(backend_env)["DB_PASSWORD"]
        root_env = self.config.path / ".env"
        secrets_module.write_private(
            root_env, secrets_module.HEADER + render(db_password)
        )
        secrets_module.ensure_gitignored(root_env)

    def _customize_projects(self) -> None:
        """Customize both backend and frontend projects."""
        # Update backend configuration
        backend_pyproject = self.config.path / "backend" / "pyproject.toml"
        if backend_pyproject.exists():
            self.update_file_regex(
                backend_pyproject,
                r'name = "django-ninja-boilerplate"',
                f'name = "{self.config.name}-backend"',
            )

        # Update frontend package.json
        frontend_package = self.config.path / "frontend" / "package.json"
        if frontend_package.exists():
            self.update_file_regex(
                frontend_package,
                r'"name": "[^"]+"',
                f'"name": "{self.config.name}-frontend"',
            )

        print_success("Customized backend and frontend projects")

    def _cleanup(self) -> None:
        """Clean up unnecessary files."""
        # Remove CLI directory from backend if it was copied
        cli_dir = self.config.path / "backend" / "cli"
        if cli_dir.exists():
            import shutil

            shutil.rmtree(cli_dir)


def generate_monorepo(config: ProjectConfig) -> bool:
    """Generate a monorepo fullstack project.

    Args:
        config: Project configuration

    Returns:
        True if successful
    """
    generator = MonorepoGenerator(config)
    return generator.run()
