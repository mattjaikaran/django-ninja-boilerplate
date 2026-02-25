# Makefile for Django Ninja Boilerplate with UV Package Management

.PHONY: help build up down logs shell migrate createsuperuser test lint format clean install sync doctor quickstart quickstart-minimal quickstart-local quickstart-ci test-contract test-contract-full local-test-contract test-load test-load-quick test-load-moderate test-load-heavy test-load-stress test-load-custom test-all test-ci

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

up-realtime: ## Start with Centrifugo real-time server
	$(DOCKER_COMPOSE) --profile realtime up -d

up-full: ## Start all services including Celery, monitoring, and realtime
	$(DOCKER_COMPOSE) --profile celery --profile monitoring --profile realtime up -d

down: ## Stop the development environment
	$(DOCKER_COMPOSE) down

down-full: ## Stop all services including profiled services
	$(DOCKER_COMPOSE) --profile celery --profile monitoring --profile realtime down

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
	@echo "  Django Ninja Boilerplate - Setup"
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

# ===========================================
# Quickstart - Fastest Clone-to-Running Experience
# ===========================================
quickstart: ## Fastest setup: clone -> running API in <2 minutes
	@./scripts/quickstart.sh

quickstart-minimal: ## Quickstart with minimal data (faster)
	@./scripts/quickstart.sh --minimal

quickstart-local: ## Quickstart without Docker (local Python)
	@./scripts/quickstart.sh --no-docker

quickstart-ci: ## Quickstart for CI environments (no browser, no prompts)
	@./scripts/quickstart.sh --ci

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

# ===========================================
# Status and Monitoring Commands
# ===========================================
status: ## Show status of all services
	@echo "========================================"
	@echo "  Service Status"
	@echo "========================================"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "========================================"
	@echo "  Port Status"
	@echo "========================================"
	@echo "Django API:  http://localhost:8000"
	@echo "API Docs:    http://localhost:8000/api/docs"
	@echo "Admin:       http://localhost:8000/admin"
	@echo "Flower:      http://localhost:5555 (if running)"
	@echo "PostgreSQL:  localhost:5432"
	@echo "Redis:       localhost:6379"

logs-error: ## Show only error logs from all services
	$(DOCKER_COMPOSE) logs -f 2>&1 | grep -i -E "(error|exception|traceback|critical|fatal)"

logs-tail: ## Show last 100 lines of logs
	$(DOCKER_COMPOSE) logs --tail=100

logs-since: ## Show logs since timestamp (usage: make logs-since TIME="1h")
	$(DOCKER_COMPOSE) logs --since=$(TIME)

# ===========================================
# Advanced Restart Commands
# ===========================================
restart-all: ## Graceful restart of all services with health verification
	@echo "Gracefully restarting all services..."
	$(DOCKER_COMPOSE) stop
	$(DOCKER_COMPOSE) up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@$(MAKE) health
	@echo "Restart complete!"

restart-db: ## Restart database service
	$(DOCKER_COMPOSE) restart $(DB_SERVICE)

restart-redis: ## Restart Redis service
	$(DOCKER_COMPOSE) restart $(REDIS_SERVICE)

restart-celery: ## Restart Celery services
	$(DOCKER_COMPOSE) restart $(CELERY_WORKER_SERVICE) $(CELERY_BEAT_SERVICE)

# ===========================================
# Docker Image Analysis
# ===========================================
image-size: ## Show Docker image sizes
	@echo "========================================"
	@echo "  Docker Image Sizes"
	@echo "========================================"
	@docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep -E "(django|ninja|boilerplate|SIZE)"

image-layers: ## Show image layers (usage: make image-layers IMAGE=django-ninja-boilerplate-django)
	docker history $(IMAGE) --no-trunc

build-stats: ## Show build cache and disk usage
	@echo "========================================"
	@echo "  Docker Build Stats"
	@echo "========================================"
	@docker system df
	@echo ""
	@echo "Build cache:"
	@docker builder du --verbose 2>/dev/null || echo "BuildKit not available"

prune-builds: ## Clean build cache
	docker builder prune -f

# ===========================================
# Performance Testing
# ===========================================
benchmark: ## Run basic API benchmark (requires curl)
	@echo "Running API benchmark..."
	@echo "Health endpoint (10 requests):"
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -s -o /dev/null -w "%{time_total}s\n" http://localhost:8000/api/health/; \
	done | awk '{sum+=$$1; count++} END {print "Average: " sum/count "s"}'

# ===========================================
# Pre-commit Hooks
# ===========================================
pre-commit-install: ## Install pre-commit hooks
	$(UV) run pre-commit install
	$(UV) run pre-commit install --hook-type commit-msg

pre-commit-update: ## Update pre-commit hooks to latest versions
	$(UV) run pre-commit autoupdate

pre-commit-all: ## Run pre-commit on all files
	$(UV) run pre-commit run --all-files

# ===========================================
# Documentation
# ===========================================
docs-serve: ## Serve documentation locally (if using mkdocs)
	$(UV) run mkdocs serve

# ===========================================
# CI/CD Helpers
# ===========================================
ci-lint: ## Run CI linting (non-Docker)
	$(UV) run ruff check .
	$(UV) run ruff format --check .

ci-test: ## Run CI tests (non-Docker)
	$(UV) run pytest --cov=. --cov-report=xml

ci-build: ## Build Docker image for CI
	docker build -t django-ninja-stack:ci .

ci-security: ## Run security audit
	$(UV) pip install pip-audit
	$(UV) run pip-audit

# ===========================================
# Troubleshooting
# ===========================================
debug-env: ## Show environment variables in Django container
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) env | sort

debug-python: ## Show Python and package info
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python --version
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) pip list

debug-django: ## Run Django system check
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py check

debug-db: ## Check database connectivity
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py dbshell -c "SELECT version();"

debug-redis: ## Check Redis connectivity
	$(DOCKER_COMPOSE) exec $(REDIS_SERVICE) redis-cli ping

debug-network: ## Show Docker network info
	docker network inspect django-ninja-boilerplate_app-network 2>/dev/null || docker network ls

# ===========================================
# Quick Development Workflows
# ===========================================
dev: ## Start development environment (alias for up)
	$(MAKE) up
	@echo ""
	@echo "Development server starting..."
	@echo "API: http://localhost:8000/api/docs"
	@echo ""

dev-full: ## Start full development environment with all services
	$(MAKE) up-full
	@echo ""
	@echo "Full development environment starting..."
	@echo "API:    http://localhost:8000/api/docs"
	@echo "Flower: http://localhost:5555"
	@echo ""

dev-reset: ## Reset development environment (down, clean volumes, up fresh)
	$(MAKE) down-volumes
	$(MAKE) up-build
	@sleep 10
	$(MAKE) migrate
	$(MAKE) seed-data
	@echo "Development environment reset complete!"

# ===========================================
# E2E Test Generation
# ===========================================
generate-e2e: ## Generate E2E test stubs from user journey YAML
	@echo "Generating E2E tests from user journeys..."
	$(UV) run python scripts/generate_e2e_tests.py
	@echo "Done! Review the generated tests in tests/e2e/"

generate-e2e-dry: ## Preview E2E test generation (dry run)
	$(UV) run python scripts/generate_e2e_tests.py --dry-run

test-e2e: ## Run E2E tests
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python -m pytest tests/e2e/ -v

local-test-e2e: ## Run E2E tests locally
	$(UV) run pytest tests/e2e/ -v

# ===========================================
# Contract Testing
# ===========================================
test-contract: ## Run API contract tests against OpenAPI spec
	$(UV) run pytest tests/contract/ -v -m contract

test-contract-full: ## Run all contract tests including slow schema tests
	$(UV) run pytest tests/contract/ -v

local-test-contract: ## Run contract tests locally (requires running server)
	TEST_BASE_URL=http://localhost:8000 $(UV) run pytest tests/contract/ -v -m contract

# ===========================================
# Load Testing with Locust
# ===========================================
test-load: ## Run load tests (interactive web UI)
	$(UV) run python scripts/run_load_tests.py --web

test-load-quick: ## Run quick load test (10 users, 30 seconds)
	$(UV) run python scripts/run_load_tests.py --quick --report

test-load-moderate: ## Run moderate load test (50 users, 2 minutes)
	$(UV) run python scripts/run_load_tests.py --moderate --report

test-load-heavy: ## Run heavy load test (100 users, 5 minutes)
	$(UV) run python scripts/run_load_tests.py --heavy --report

test-load-stress: ## Run stress test (200 users, 10 minutes)
	$(UV) run python scripts/run_load_tests.py --stress --report

test-load-custom: ## Run custom load test (usage: make test-load-custom USERS=50 DURATION=2m)
	$(UV) run python scripts/run_load_tests.py -u $(USERS) -t $(DURATION) --report

# ===========================================
# All Tests
# ===========================================
test-all: ## Run all test types (unit, e2e, contract)
	@echo "========================================"
	@echo "  Running All Tests"
	@echo "========================================"
	@echo ""
	@echo ">>> Running Unit Tests..."
	$(MAKE) local-test
	@echo ""
	@echo ">>> Running E2E Tests..."
	$(MAKE) local-test-e2e
	@echo ""
	@echo ">>> Running Contract Tests..."
	$(MAKE) local-test-contract
	@echo ""
	@echo "========================================"
	@echo "  All Tests Complete"
	@echo "========================================"

test-ci: ## Run tests suitable for CI (excludes load tests)
	$(UV) run pytest --cov=. --cov-report=xml -v
	$(UV) run pytest tests/e2e/ -v || true
	@echo "Contract tests require running server - skipped in CI"

# ===========================================
# OpenAPI Tools
# ===========================================
openapi: ## Export OpenAPI specification to docs/openapi/
	$(UV) run python manage.py export_openapi

openapi-validate: ## Export and validate OpenAPI specification
	$(UV) run python manage.py export_openapi --validate

openapi-all: ## Generate OpenAPI spec, SDKs, and collections
	$(UV) run python manage.py export_openapi --all

sdk: ## Generate TypeScript and Python SDK clients
	$(UV) run python manage.py export_openapi --sdk

sdk-typescript: ## Generate TypeScript SDK client only
	$(UV) run python manage.py export_openapi --sdk-typescript

sdk-python: ## Generate Python SDK client only
	$(UV) run python manage.py export_openapi --sdk-python

postman: ## Export Postman collection
	$(UV) run python manage.py export_openapi --postman

insomnia: ## Export Insomnia collection
	$(UV) run python manage.py export_openapi --insomnia

changelog: ## Generate API changelog (usage: make changelog OLD=v1.json NEW=v2.json)
	$(UV) run python scripts/openapi/generate_changelog.py $(OLD) $(NEW)

# ===========================================
# Health & Celery Convenience
# ===========================================
health: ## Check health endpoint
	@curl -s http://localhost:8000/api/health/ | python -m json.tool 2>/dev/null || echo "Server not running"

ready: ## Check readiness endpoint
	@curl -s http://localhost:8000/api/health/readiness | python -m json.tool 2>/dev/null || echo "Server not running"

seed: ## Run seed data command
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) $(UV) run python manage.py seed_data

celery-worker: ## Start Celery worker (all queues)
	$(UV) run celery -A api worker -Q default,emails,bulk -l info

celery-beat: ## Start Celery beat scheduler
	$(UV) run celery -A api beat -l info

celery-flower: ## Start Celery Flower monitoring
	$(UV) run celery -A api flower --port=5555

# ===========================================
# Version and Info
# ===========================================
version: ## Show version information
	@echo "Django Ninja Boilerplate v1.2.0"
	@echo ""
	@echo "Python: $$(python --version 2>&1)"
	@echo "UV: $$(uv --version 2>&1)"
	@echo "Docker: $$(docker --version 2>&1)"
	@echo "Docker Compose: $$(docker compose version 2>&1)"
