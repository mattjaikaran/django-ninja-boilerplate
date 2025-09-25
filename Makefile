# Makefile for Django Ninja Boilerplate

# Variables
PYTHON := python
MANAGE := $(PYTHON) manage.py
UV := uv
SCRIPTS_DIR := scripts

# Django commands
.PHONY: runserver
runserver:
	$(MANAGE) runserver

.PHONY: migrate
migrate:
	$(MANAGE) migrate

.PHONY: makemigrations
makemigrations:
	$(MANAGE) makemigrations

startapp:
	@if [ -z "$(filter-out $@,$(MAKECMDGOALS))" ]; then \
		echo "Usage: make startapp <app_name>"; \
	else \
		python manage.py startapp_extended $(filter-out $@,$(MAKECMDGOALS)); \
	fi

%:
	@:


install:
	@if [ -z "$(filter-out $@,$(MAKECMDGOALS))" ]; then \
		echo "Usage: make install <library-name>"; \
	else \
		$(UV) add $(filter-out $@,$(MAKECMDGOALS)) && \
		echo "Installed $(filter-out $@,$(MAKECMDGOALS)) and updated pyproject.toml"; \
	fi

# Install dependencies
.PHONY: sync
sync:
	$(UV) sync

# Install dev dependencies
.PHONY: sync-dev
sync-dev:
	$(UV) sync --dev

%:
	@:

# first time setup
.PHONY: first-time-setup
first-time-setup:
	@bash $(SCRIPTS_DIR)/setup.sh

.PHONY: shell
shell:
	$(MANAGE) shell

.PHONY: createsuperuser
createsuperuser:
	$(MANAGE) createsuperuser

# Create superuser custom script
.PHONY: create-superuser
create-superuser:
	$(MANAGE) create_superuser

# Testing
.PHONY: test
test:
	$(MANAGE) test

# Linting and formatting
.PHONY: lint
lint:
	$(UV) run ruff check .

.PHONY: format
format:
	$(UV) run ruff format .

.PHONY: lint-fix
lint-fix:
	$(UV) run ruff check --fix .

.PHONY: generate-core-data
generate-core-data:
	$(MANAGE) generate_core_data


# Generate secret key
.PHONY: generate-secret-key
generate-secret-key:
	@bash $(SCRIPTS_DIR)/generate_secret_key.sh

# Database setup
.PHONY: db-setup
db-setup:
	@echo "Setting up the database..."
	@bash $(SCRIPTS_DIR)/db_setup.sh

# Lint using custom script (legacy)
.PHONY: custom-lint
custom-lint:
	@bash $(SCRIPTS_DIR)/lint.sh

# Run tests with pytest
.PHONY: pytest
pytest:
	$(UV) run pytest

# Run tests with coverage
.PHONY: test-cov
test-cov:
	$(UV) run pytest --cov=.

# Collect static files
.PHONY: collectstatic
collectstatic:
	$(MANAGE) collectstatic --noinput


# Help command
.PHONY: help
help:
	@echo "Available commands:"
	@echo "  runserver                  - Run the Django development server"
	@echo "  migrate                    - Apply database migrations"
	@echo "  makemigrations             - Create new database migrations"
	@echo "  startapp                   - Start a new Django app"
	@echo "  first-time-setup           - First time setup"
	@echo "  install                    - Install a library using uv"
	@echo "  sync                       - Install dependencies from pyproject.toml"
	@echo "  sync-dev                   - Install dev dependencies"
	@echo "  shell                      - Open Django shell"
	@echo "  createsuperuser            - Create a superuser"
	@echo "  create-superuser           - Create a superuser using custom script"
	@echo "  test                       - Run the Django test suite"
	@echo "  pytest                     - Run tests with pytest"
	@echo "  test-cov                   - Run tests with coverage"
	@echo "  lint                       - Run linting with ruff"
	@echo "  format                     - Run formatter with ruff"
	@echo "  lint-fix                   - Run linting with auto-fix"
	@echo "  generate-core-data         - Generate core data"
	@echo "  generate-secret-key        - Generate secret key"
	@echo "  db-setup                   - Setup the database"
	@echo "  custom-lint                - Run custom lint (legacy)"
	@echo "  collectstatic              - Collect static files"
