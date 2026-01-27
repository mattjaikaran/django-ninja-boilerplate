# Makefile for Django Ninja Boilerplate with UV Package Management

.PHONY: help build up down logs shell migrate createsuperuser test lint format clean install sync doctor

# Variables
DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_PROD = docker-compose -f docker-compose.prod.yml
DOCKER_COMPOSE_SINGLE = docker-compose -f docker-compose.single.yml
DJANGO_SERVICE = django
DB_SERVICE = db
REDIS_SERVICE = redis
CELERY_WORKER_SERVICE = celery-worker
CELERY_BEAT_SERVICE = celery-beat
FLOWER_SERVICE = flower
UV = uv

# Default target
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development commands
build: ## Build the Docker images
	$(DOCKER_COMPOSE) build

up: ## Start the development environment
	$(DOCKER_COMPOSE) up -d

up-build: ## Build and start the development environment
	$(DOCKER_COMPOSE) up -d --build

up-celery: ## Start with Celery workers (db, redis, django, celery-worker, celery-beat)
	$(DOCKER_COMPOSE) --profile celery up -d

up-monitoring: ## Start with monitoring tools (includes Flower)
	$(DOCKER_COMPOSE) --profile monitoring up -d

up-full: ## Start all services including Celery and monitoring
	$(DOCKER_COMPOSE) --profile celery --profile monitoring up -d

down: ## Stop the development environment
	$(DOCKER_COMPOSE) down

down-full: ## Stop all services including profiled services
	$(DOCKER_COMPOSE) --profile celery --profile monitoring down

down-volumes: ## Stop the development environment and remove volumes
	$(DOCKER_COMPOSE) down -v

logs: ## Show logs for all services
	$(DOCKER_COMPOSE) logs -f

logs-django: ## Show logs for the django service
	$(DOCKER_COMPOSE) logs -f $(DJANGO_SERVICE)

logs-db: ## Show logs for the database service
	$(DOCKER_COMPOSE) logs -f $(DB_SERVICE)

logs-redis: ## Show logs for the redis service
	$(DOCKER_COMPOSE) logs -f $(REDIS_SERVICE)

# Django management commands
shell: ## Open Django shell
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py shell

shell-plus: ## Open Django shell with shell_plus (if available)
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py shell_plus

migrate: ## Run Django migrations
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py migrate

makemigrations: ## Create Django migrations
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py makemigrations

createsuperuser: ## Create Django superuser with default command
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py createsuperuser

create-superuser: ## Create Django superuser with custom command located in core/management/commands/create_superuser.py
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py create_superuser

collectstatic: ## Collect static files
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py collectstatic --noinput

# Database commands
db-shell: ## Open database shell
	$(DOCKER_COMPOSE) exec $(DB_SERVICE) psql -U postgres -d boilerplate_db

db-backup: ## Backup database
	$(DOCKER_COMPOSE) exec $(DB_SERVICE) pg_dump -U postgres boilerplate_db > backup_$$(date +%Y%m%d_%H%M%S).sql

db-restore: ## Restore database (usage: make db-restore FILE=backup.sql)
	$(DOCKER_COMPOSE) exec -T $(DB_SERVICE) psql -U postgres -d boilerplate_db < $(FILE)

# Redis commands
redis-cli: ## Open Redis CLI
	$(DOCKER_COMPOSE) exec $(REDIS_SERVICE) redis-cli

redis-flush: ## Flush Redis cache
	$(DOCKER_COMPOSE) exec $(REDIS_SERVICE) redis-cli FLUSHALL

# Celery commands
celery-worker: ## Start Celery worker
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run celery -A api worker -l info

celery-beat: ## Start Celery beat scheduler
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run celery -A api beat -l info

celery-flower: ## Start Flower monitoring (Celery dashboard)
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run celery -A api flower --port=5555

celery-inspect: ## Inspect active Celery tasks
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run celery -A api inspect active

celery-purge: ## Purge all Celery tasks
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run celery -A api purge -f

# Package Management with UV
install: ## Install dependencies with UV
	$(UV) pip install -e .

sync: ## Sync dependencies with UV
	$(UV) pip sync

install-dev: ## Install development dependencies
	$(UV) pip install -e ".[dev]"

add: ## Add a new dependency (usage: make add PACKAGE=package-name)
	$(UV) add $(PACKAGE)

add-dev: ## Add a new development dependency (usage: make add-dev PACKAGE=package-name)
	$(UV) add --dev $(PACKAGE)

lock: ## Update lock file
	$(UV) lock

# Testing and quality
test: ## Run tests
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python -m pytest

test-coverage: ## Run tests with coverage
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python -m pytest --cov=. --cov-report=html

test-watch: ## Run tests in watch mode
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python -m pytest --watch

lint: ## Run linting with Ruff
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run ruff check .

lint-fix: ## Run linting with auto-fix
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run ruff check --fix .

format: ## Format code with Ruff
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run ruff format .

format-check: ## Check code formatting
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run ruff format --check .

mypy: ## Run type checking with mypy
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run mypy .

pre-commit: ## Run pre-commit hooks
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run pre-commit run --all-files

# Production commands
prod-build: ## Build production images
	$(DOCKER_COMPOSE_PROD) build

prod-up: ## Start production environment (split services)
	$(DOCKER_COMPOSE_PROD) up -d

prod-down: ## Stop production environment
	$(DOCKER_COMPOSE_PROD) down

prod-logs: ## Show production logs
	$(DOCKER_COMPOSE_PROD) logs -f

# Single-container production (for PaaS/simpler deployments)
single-build: ## Build single-container production image
	$(DOCKER_COMPOSE_SINGLE) build

single-up: ## Start single-container production environment
	$(DOCKER_COMPOSE_SINGLE) up -d

single-down: ## Stop single-container production environment
	$(DOCKER_COMPOSE_SINGLE) down

single-logs: ## Show single-container logs
	$(DOCKER_COMPOSE_SINGLE) logs -f

# Utility commands
clean: ## Clean up Docker resources
	docker system prune -f
	docker volume prune -f

clean-all: ## Clean up all Docker resources (images, volumes, networks)
	docker system prune -a -f
	docker volume prune -f

restart: ## Restart all services
	$(DOCKER_COMPOSE) restart

restart-django: ## Restart django service
	$(DOCKER_COMPOSE) restart $(DJANGO_SERVICE)

# Health checks
health: ## Check service health
	@echo "Checking service health..."
	@curl -f http://localhost:8000/api/health/ || echo "Web service not responding"

doctor: ## Validate development environment (Python, Docker, ports, config)
	@./scripts/doctor.sh

# Development tools
shell-uv: ## Open UV shell with project dependencies
	$(UV) shell

run-server: ## Run Django development server with UV
	$(UV) run python manage.py runserver

# Data management
flush-db: ## Flush database
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py flush --noinput

reset-migrations: ## Reset all migrations (DANGEROUS!)
	@echo "This will delete all migration files. Are you sure? (y/N)"
	@read confirm && [ "$$confirm" = "y" ] || exit 1
	find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
	find . -path "*/migrations/*.pyc" -delete
	$(MAKE) makemigrations

seed-data: ## Load comprehensive seed data
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py seed_data

seed-data-full: ## Load comprehensive seed data with higher counts
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py seed_data --full

seed-data-clear: ## Clear and reload all seed data
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py seed_data --clear

seed-core: ## Load core seed data only (legacy)
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py generate_core_data

create-fixtures: ## Create fixtures from current data
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py dumpdata --indent=2 > fixtures/current_data.json

# Database dump/restore commands
db-dump: ## Create a database dump
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py db_dump dump

db-dump-data: ## Create a data-only database dump
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py db_dump dump --data-only

db-dump-schema: ## Create a schema-only database dump
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py db_dump dump --schema-only

db-dump-compressed: ## Create a compressed database dump
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py db_dump dump --compress

db-restore: ## Restore database from dump (usage: make db-restore FILE=docker/postgres/dumps/dump.sql)
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py db_dump restore $(FILE)

db-list-dumps: ## List available database dumps
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py db_dump list

db-clean-dumps: ## Clean old database dumps, keeping 5 most recent
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py db_dump clean --keep 5

# Monitoring
monitor: ## Open monitoring dashboard
	@echo "Opening monitoring tools..."
	@echo "Django Admin: http://localhost:8000/admin"
	@echo "API Docs: http://localhost:8000/api/docs"

# Setup commands
setup: ## One-command project bootstrap (runs doctor, builds, migrates, seeds)
	@echo "========================================"
	@echo "  Django Ninja Stack - Setup"
	@echo "========================================"
	@./scripts/setup.sh --auto

setup-interactive: ## Interactive setup with prompts
	@./scripts/setup.sh

setup-env: ## Create .env file from example
	@if [ ! -f .env ]; then \
		if [ -f .env.example ]; then \
			cp .env.example .env; \
		elif [ -f env.example ]; then \
			cp env.example .env; \
		else \
			cp .env.development .env 2>/dev/null || echo "# Django Ninja Boilerplate Environment Variables" > .env; \
		fi; \
		echo ".env file created"; \
	else \
		echo ".env file already exists"; \
	fi

quick-setup: ## Quick setup (up + migrate only, assumes .env exists)
	$(MAKE) up
	@echo "Waiting for services to start..."
	@sleep 10
	$(MAKE) migrate

check: ## Run all checks (lint, format-check, test)
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) test

fix: ## Fix all auto-fixable issues
	$(MAKE) lint-fix
	$(MAKE) format

# App generation commands
startapp: ## Create a new Django app with extended structure (usage: make startapp APP=myapp)
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py startapp_extended $(APP)

generate-feature: ## Generate a feature module (usage: make generate-feature FEATURE=payments PROVIDER=stripe)
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py generate_feature $(FEATURE) $(if $(PROVIDER),--provider $(PROVIDER),) $(if $(PLATFORM),--platform-type $(PLATFORM),)

# Data generation
generate-data: ## Generate sample data for development
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py generate_core_data

generate-todos: ## Generate sample todo data
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py generate_todos_data

# Security commands
security-check: ## Run security checks
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py check --deploy

# Export/Import commands
export-data: ## Export all data to fixtures (usage: make export-data APP=core)
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py dumpdata $(APP) --indent=2 > fixtures/$(APP)_data.json

import-data: ## Import data from fixture (usage: make import-data FILE=fixtures/data.json)
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py loaddata $(FILE)

# Shell commands
ipython: ## Open IPython shell
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py shell_plus --ipython

# Shortcuts for local development (without Docker)
local-run: ## Run Django dev server locally
	$(UV) run python manage.py runserver

local-migrate: ## Run migrations locally
	$(UV) run python manage.py migrate

local-makemigrations: ## Create migrations locally
	$(UV) run python manage.py makemigrations

local-shell: ## Open Django shell locally
	$(UV) run python manage.py shell

local-test: ## Run tests locally
	$(UV) run pytest

local-lint: ## Run linting locally
	$(UV) run ruff check .

local-format: ## Format code locally
	$(UV) run ruff format .

local-celery: ## Start Celery worker locally
	$(UV) run celery -A api worker -l info

# Docker shortcuts
exec: ## Execute a command in Django container (usage: make exec CMD="python manage.py showmigrations")
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run $(CMD)