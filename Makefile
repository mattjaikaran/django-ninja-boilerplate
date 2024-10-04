# Makefile for Django Ninja Video Streaming Platform

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

.PHONY: shell
shell:
	$(MANAGE) shell

.PHONY: createsuperuser
createsuperuser:
	$(MANAGE) createsuperuser


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

.PHONY: generate_core_data
generate_core_data:
	$(MANAGE) generate_core_data
