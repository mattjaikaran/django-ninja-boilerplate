# Django Ninja Boilerplate v1.11.0 — developer tasks
#
# The previous Makefile is kept at Makefile.legacy for anything not ported here.
# Run `just` with no arguments (or `just help`) to list every recipe.

set shell := ["bash", "-cu"]

compose := "docker compose"
dev := compose + " --profile dev"
uv := "uv"
django_service := "django"
db_service := "db"

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

# List every recipe
help:
    @just --list

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

# Start the dev stack (db, valkey, django, mcp, mailhog)
dev:
    {{ dev }} up -d

# Follow logs for the whole dev stack
dev-logs:
    {{ dev }} logs -f

# Stop the dev stack
down:
    {{ dev }} down

# Stop the dev stack and remove its volumes
down-volumes:
    {{ dev }} down -v

# Restart the dev stack from scratch: down, up, migrate
reset: down
    {{ dev }} up -d
    just migrate

# Build every image, including the profiled services
build:
    {{ compose }} --profile dev --profile prod --profile single build

# Start the dev stack (alias for `dev`)
up:
    {{ dev }} up -d

# Build images and start the dev stack
up-build:
    {{ dev }} up -d --build

# Start the dev stack with Celery workers
up-celery:
    {{ compose }} --profile dev --profile celery up -d

# Start the dev stack with monitoring (Flower, Jaeger)
up-monitoring:
    {{ compose }} --profile dev --profile monitoring up -d

# Start the dev stack with Centrifugo
up-realtime:
    {{ compose }} --profile dev --profile realtime up -d

# Start every dev service
up-full:
    {{ compose }} --profile dev --profile celery --profile monitoring --profile realtime up -d

# Stop every dev service
down-full:
    {{ compose }} --profile dev --profile celery --profile monitoring --profile realtime down

# Stop every dev service and remove volumes
down-volumes-full:
    {{ compose }} --profile dev --profile celery --profile monitoring --profile realtime down -v

# Follow logs for the dev stack
logs:
    {{ dev }} logs -f

# Follow Django logs
logs-django:
    {{ dev }} logs -f {{ django_service }}

# Open the Django shell with shell_plus
shell-plus:
    {{ dev }} exec {{ django_service }} {{ uv }} run python manage.py shell_plus

# Create a superuser with the project's command
create-superuser:
    {{ dev }} exec {{ django_service }} {{ uv }} run python manage.py create_superuser

# Install the pre-commit hooks (pre-commit and commit-msg)
pre-commit-install:
    {{ uv }} run pre-commit install
    {{ uv }} run pre-commit install --hook-type commit-msg

# Create a .env file from the example
setup-env:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -f .env ]; then
        echo ".env already exists; leaving it alone."
    else
        cp .env.example .env
        echo "Created .env from .env.example."
    fi

# Format code (alias for `fmt`)
format: fmt

# Type-check with ty
ty:
    {{ uv }} run ty check .

# Alias for `test`
test-all:
    {{ uv }} run pytest

# Run any target from the legacy Makefile, with its arguments:
#   just legacy db-dump
# just legacy startapp APP=myapp
legacy +target:
    make -f Makefile.legacy {{ target }}

# List every legacy Makefile target
targets:
    make -f Makefile.legacy help

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

# Run the test suite on SQLite (fast, no services)
test:
    {{ uv }} run pytest

# Run the test suite with coverage
test-coverage:
    {{ uv }} run pytest --cov=core --cov=todos --cov=decisions --cov-report=term-missing

# Run the decisions app tests
test-decisions:
    {{ uv }} run pytest decisions/ -v

# Run the full suite against Postgres + pgvector, then tear down.
# Host ports are offset from the defaults so this works while a local
# Postgres (5432) or Valkey (6379) is already running.
test-integration:
    #!/usr/bin/env bash
    set -euo pipefail
    pg_port="${TEST_POSTGRES_PORT:-5434}"
    valkey_port="${TEST_VALKEY_PORT:-6381}"
    trap 'POSTGRES_PORT=$pg_port VALKEY_PORT=$valkey_port {{ compose }} --profile test down' EXIT
    POSTGRES_PORT=$pg_port VALKEY_PORT=$valkey_port {{ compose }} --profile test up -d --wait {{ db_service }} valkey
    DB_HOST=127.0.0.1 DB_PORT=$pg_port CI=1 {{ uv }} run pytest

# Re-run tests whenever a Python file changes (polls, needs no extra tools)
test-watch:
    #!/usr/bin/env bash
    set -euo pipefail
    stamp=$(mktemp)
    trap 'rm -f "$stamp"' EXIT
    touch "$stamp"
    while true; do
        {{ uv }} run pytest -q || true
        while :; do
            sleep 2
            changed=$(find . -path ./.venv -prune -o -name '*.py' -newer "$stamp" -print -quit)
            if [ -n "$changed" ]; then
                touch "$stamp"
                break
            fi
        done
    done

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Run Django migrations
migrate:
    {{ dev }} exec {{ django_service }} {{ uv }} run python manage.py migrate

# Create Django migrations
makemigrations:
    {{ dev }} exec {{ django_service }} {{ uv }} run python manage.py makemigrations

# Open the Django shell
shell:
    {{ dev }} exec {{ django_service }} {{ uv }} run python manage.py shell

# Open a psql shell on the dev database
db-shell:
    {{ dev }} exec {{ db_service }} psql -U postgres -d boilerplate_db

# Load the decisions fixtures
seed-decisions:
    {{ dev }} exec {{ django_service }} {{ uv }} run python manage.py seed_decisions

# Load development sample data (users, todos)
seed:
    {{ dev }} exec {{ django_service }} {{ uv }} run python manage.py seed_data

# Regenerate the codebase atlas data file
update-architecture:
    {{ dev }} exec {{ django_service }} {{ uv }} run python manage.py atlas

# Validate the development environment
doctor:
    ./scripts/doctor.sh

# ---------------------------------------------------------------------------
# MCP
# ---------------------------------------------------------------------------

# Start the django-ai-boost SSE server on port 8001
mcp:
    {{ dev }} up -d mcp

# Follow MCP server logs
mcp-logs:
    {{ dev }} logs -f mcp

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

# Search the repo with ripgrep
search pattern *paths='.':
    rg --smart-case {{ pattern }} {{ paths }}

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

# Lint with Ruff
lint:
    {{ uv }} run ruff check .

# Lint and apply safe fixes
lint-fix:
    {{ uv }} run ruff check . --fix

# Format with Ruff
fmt:
    {{ uv }} run ruff format .

# Check formatting without writing
format-check:
    {{ uv }} run ruff format --check .

# Type-check with mypy
typecheck:
    {{ uv }} run mypy .

# Run the quick gauntlet (skips mutation testing and audit)
check-all:
    {{ uv }} run python scripts/gauntlet.py --quick --verbose

# Run the quick gauntlet
gauntlet-quick:
    {{ uv }} run python scripts/gauntlet.py --quick --verbose

# Run every gauntlet gate
gauntlet:
    {{ uv }} run python scripts/gauntlet.py --verbose

# Run the gauntlet in CI mode with a JSON report
gauntlet-ci:
    {{ uv }} run python scripts/gauntlet.py --ci --report

# Run one gauntlet gate (for example: just gauntlet-gate lint)
gauntlet-gate gate:
    {{ uv }} run python scripts/gauntlet.py --gate {{ gate }} --verbose

# Check code conventions
check-conventions:
    {{ uv }} run python scripts/check_conventions.py

# Check cross-stack consistency
check-cross-stack:
    {{ uv }} run python scripts/check_cross_stack.py

# Check architecture constraints
check-arch:
    {{ uv }} run python scripts/check_architecture.py --all

# Run mutation testing
mutation-test:
    {{ uv }} run mutmut run

# Run the security scan
security-scan:
    {{ uv }} run bandit -c pyproject.toml -r .

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# One-command bootstrap: .env, secret key, doctor, build, migrate, superuser
setup: setup-env
    ./scripts/generate_secret_key.sh --update-env
    ./scripts/doctor.sh
    # --wait keeps `just migrate` from racing the container's own migrate.
    {{ dev }} up -d --build --wait
    just migrate
    just create-superuser
    just wait-for-api

# Wait until the API answers its health check
wait-for-api:
    #!/usr/bin/env bash
    set -euo pipefail
    for _ in $(seq 1 60); do
        if curl -fsS http://localhost:8000/api/health/ >/dev/null 2>&1; then
            echo "API is up: http://localhost:8000/api/docs"
            exit 0
        fi
        sleep 1
    done
    echo "The API did not answer /api/health/ within 60s." >&2
    echo "Check the logs with: just logs-django" >&2
    exit 1

# Clone to running API in under two minutes
quickstart:
    ./scripts/quickstart.sh

# Quickstart with minimal seed data
quickstart-minimal:
    ./scripts/quickstart.sh --minimal

# Quickstart without Docker (local Python)
quickstart-local:
    ./scripts/quickstart.sh --no-docker

# Quickstart for CI: no browser, no prompts
quickstart-ci:
    ./scripts/quickstart.sh --ci

# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------

# Build the production images
prod-build:
    {{ compose }} --profile prod build

# Start the production stack
prod-up:
    {{ compose }} --profile prod up -d

# Stop the production stack
prod-down:
    {{ compose }} --profile prod down

# Follow production logs
prod-logs:
    {{ compose }} --profile prod logs -f

# Build the single-container production image
single-build:
    {{ compose }} --profile single build

# Start the single-container stack
single-up:
    {{ compose }} --profile single up -d

# Stop the single-container stack
single-down:
    {{ compose }} --profile single down

# Follow single-container logs
single-logs:
    {{ compose }} --profile single logs -f

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

# Deploy to the configured provider (set DEPLOY_PROVIDER in .env.deploy)
deploy:
    ./scripts/deploy.sh

# Show what deploy would do without executing
deploy-dry-run:
    ./scripts/deploy.sh --dry-run

# Deploy to a VPS over SSH
deploy-vps:
    ./scripts/deploy.sh --provider vps

# Deploy with pre-deploy lint and tests
deploy-safe:
    ./scripts/deploy.sh --provider vps --skip-checks=false

# One-time setup: install provider CLIs and authenticate
deploy-setup:
    ./scripts/deploy-setup.sh

# Bump the version and cut a release (commits, tags, and pushes)
release:
    {{ uv }} run python scripts/release.py

# Preview the version bump without writing anything
release-dry-run:
    {{ uv }} run python scripts/release.py --dry-run

# Check deployment status for the configured provider
deploy-status:
    ./scripts/deploy.sh --status

# Tail deployment logs for the configured provider
deploy-logs:
    ./scripts/deploy.sh --logs

# Roll back to the previous deployment
deploy-rollback:
    ./scripts/deploy.sh --rollback
