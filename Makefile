# Makefile for Django Ninja Boilerplate

# Variables
PYTHON := python
MANAGE := $(PYTHON) manage.py
PIP := pip
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
		pip install $(filter-out $@,$(MAKECMDGOALS)) && \
		pip freeze > requirements.txt && \
		echo "Installed $(filter-out $@,$(MAKECMDGOALS)) and updated requirements.txt"; \
	fi

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
	flake8 .

.PHONY: format
format:
	black .

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

# Lint using custom script
.PHONY: custom-lint
custom-lint:
	@bash $(SCRIPTS_DIR)/lint.sh

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
	@echo "  install                    - Install a library"
	@echo "  shell                      - Open Django shell"
	@echo "  createsuperuser            - Create a superuser"
	@echo "  create-superuser           - Create a superuser using custom script"
	@echo "  test                       - Run the Django test suite"
	@echo "  lint                       - Run linting"
	@echo "  format                     - Run formatter"
	@echo "  generate-core-data         - Generate core data"
	@echo "  generate-secret-key        - Generate secret key"
	@echo "  db-setup                   - Setup the database"
	@echo "  custom-lint                - Run custom lint"
	@echo "  collectstatic              - Collect static files"
