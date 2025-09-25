# Makefile for Django Ninja Boilerplate with UV Package Management

.PHONY: help build up down logs shell migrate createsuperuser test lint format clean install sync

# Variables
DOCKER_COMPOSE = docker-compose
DOCKER_COMPOSE_PROD = docker-compose -f docker-compose.prod.yml
DJANGO_SERVICE = django
DB_SERVICE = db
REDIS_SERVICE = redis
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

down: ## Stop the development environment
	$(DOCKER_COMPOSE) down

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
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) python manage.py shell

shell-plus: ## Open Django shell with shell_plus (if available)
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) python manage.py shell_plus

migrate: ## Run Django migrations
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) python manage.py migrate

makemigrations: ## Create Django migrations
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) python manage.py makemigrations

createsuperuser: ## Create Django superuser
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) python manage.py createsuperuser

collectstatic: ## Collect static files
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) python manage.py collectstatic --noinput

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

prod-up: ## Start production environment
	$(DOCKER_COMPOSE_PROD) up -d

prod-down: ## Stop production environment
	$(DOCKER_COMPOSE_PROD) down

prod-logs: ## Show production logs
	$(DOCKER_COMPOSE_PROD) logs -f

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

# Development tools
shell-uv: ## Open UV shell with project dependencies
	$(UV) shell

run-server: ## Run Django development server with UV
	$(UV) run python manage.py runserver

# Data management
flush-db: ## Flush database
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) python manage.py flush --noinput

reset-migrations: ## Reset all migrations (DANGEROUS!)
	@echo "This will delete all migration files. Are you sure? (y/N)"
	@read confirm && [ "$$confirm" = "y" ] || exit 1
	find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
	find . -path "*/migrations/*.pyc" -delete
	$(MAKE) makemigrations

seed-data: ## Load seed data
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) python manage.py generate_core_data

create-fixtures: ## Create fixtures from current data
	$(DOCKER_COMPOSE) exec $(DJANGO_SERVICE) python manage.py dumpdata --indent=2 > fixtures/current_data.json

# Monitoring
monitor: ## Open monitoring dashboard
	@echo "Opening monitoring tools..."
	@echo "Django Admin: http://localhost:8000/admin"
	@echo "API Docs: http://localhost:8000/api/docs"

# Setup commands
setup: ## Initial setup for development
	@echo "Setting up development environment..."
	$(MAKE) setup-env
	$(MAKE) build
	$(MAKE) up
	@echo "Waiting for services to start..."
	@sleep 10
	$(MAKE) migrate
	$(MAKE) seed-data
	@echo "Setup complete! Visit http://localhost:8000"

setup-env: ## Create .env file from example
	@if [ ! -f .env ]; then \
		cp env.example .env 2>/dev/null || echo "# Django Ninja Boilerplate Environment Variables" > .env; \
		echo ".env file created"; \
		echo "Please edit .env file with your configuration"; \
	else \
		echo ".env file already exists"; \
	fi

quick-setup: ## Quick setup without building
	$(MAKE) up
	$(MAKE) migrate

check: ## Run all checks (lint, format-check, test)
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) test

fix: ## Fix all auto-fixable issues
	$(MAKE) lint-fix
	$(MAKE) format