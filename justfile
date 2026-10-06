# Django Ninja Boilerplate v1.12.0 — developer tasks
#
# The previous Makefile is kept at Makefile.legacy for anything not ported here.
# Run `just` with no arguments (or `just help`) to list every recipe.

set shell := ["bash", "-cu"]

compose := "docker compose"
dev := compose + " --profile dev"
uv := "uv"
django_service := "django"
db_service := "db"

# Image label version. Compose passes it to the Dockerfiles as a build arg.
export APP_VERSION := trim(read("VERSION"))

# Optional extras baked into the images, space-separated:
# `UV_EXTRAS="sentry" just prod-build`, or UV_EXTRAS=sentry in .env. Not
# exported here: an exported empty value would override .env. Compose and
# `just trivy` pass it to the Dockerfiles as a build arg.

# Extras the test suite imports: the task contract test loads every backend.
test_extras := "--extra dev --extra huey --extra django-q --extra django-rq --extra dramatiq"

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

# List every recipe
help:
    @just --list

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

# Compose profile for the task backend selected in .env. TASK_BACKEND is the
# single switch: Docker passes it to Django (env_file) and the worker services
# pin it, so changing it in .env changes both sides consistently.
backend-profile:
    #!/usr/bin/env bash
    set -euo pipefail
    name=$(grep -E '^TASK_BACKEND=' .env 2>/dev/null | tail -1 | cut -d= -f2 || true)
    case "${name:-celery}" in
        celery) echo celery ;;
        huey) echo huey ;;
        # The loader (api/tasks/loader.py) accepts only the underscore names.
        django_q) echo django-q ;;
        django_rq) echo django-rq ;;
        dramatiq) echo dramatiq ;;
        # No worker profile: the dev profile alone starts db, valkey, django.
        none) echo dev ;;
        *)
            echo "Unknown TASK_BACKEND '${name}' in .env" >&2
            echo "Expected one of: celery, huey, django_q, django_rq, dramatiq, none" >&2
            exit 1
            ;;
    esac

# Run Compose with the dev profile plus the task worker profile selected in
# .env. Every dev stack recipe goes through this one.
_stack *args:
    #!/usr/bin/env bash
    set -euo pipefail
    {{ compose }} --profile dev --profile "$(just backend-profile)" {{ args }}

# Start the dev stack: db, valkey, django, and the configured task worker.
# `--build` builds missing images and rebuilds images whose inputs changed,
# such as uv.lock after a pull. Cached builds take a few seconds.
dev:
    just _stack up -d --build

# Follow logs for the whole dev stack
dev-logs:
    {{ dev }} logs -f

# Stop the dev stack
down:
    just _stack down

# Stop the dev stack and remove its volumes
down-volumes:
    just _stack down -v

# Restart the dev stack from scratch: down, up, migrate
reset: down
    just _stack up -d --build
    just migrate

# Build the application images and the selected task worker
build:
    just _stack --profile prod --profile single build

# Start the dev stack (alias for `dev`)
up:
    just dev

# Start the dev stack with monitoring (Flower, Jaeger)
up-monitoring:
    just _stack --profile monitoring up -d --build

# Start the dev stack with Centrifugo
up-realtime:
    just _stack --profile realtime up -d --build

# Start the dev stack with Mailhog. Point EMAIL_* at mailhog in .env first;
# see the Email Settings block in .env.example.
up-mail:
    just _stack --profile mail up -d --build

# Start the dev stack with the MCP server (needs the `dev` extra and
# DJANGO_MCP_AUTH_TOKEN in .env)
up-mcp: _mcp-token
    just _stack --profile mcp up -d --build

# Start every dev service
up-full: _mcp-token
    just _stack --profile monitoring --profile realtime --profile mail --profile mcp up -d --build

# Stop every dev service
down-full:
    just _stack --profile monitoring --profile realtime --profile mail --profile mcp down

# Stop every dev service and remove volumes
down-volumes-full:
    just _stack --profile monitoring --profile realtime --profile mail --profile mcp down -v

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

# Hooks come from .pre-commit-config.yaml and go into this clone only.
# pre-commit refuses to install while core.hooksPath is set. When it only
# names this clone's default .git/hooks, the recipe unsets that local entry
# (same directory, no behavior change); any other hooks path stops the install.
# Install the pre-commit, commit-msg and pre-push (gauntlet-quick) git hooks
pre-commit-install:
    #!/usr/bin/env bash
    set -euo pipefail
    hooks_path=$(git config --local core.hooksPath || true)
    if [ -n "$hooks_path" ]; then
        default=$(git rev-parse --absolute-git-dir)/hooks
        if [ "$(cd "$hooks_path" 2>/dev/null && pwd -P)" != "$(cd "$default" && pwd -P)" ]; then
            echo "core.hooksPath is $hooks_path, not this clone's .git/hooks; not installing." >&2
            exit 1
        fi
        git config --local --unset core.hooksPath
    fi
    {{ uv }} run --extra dev pre-commit install

# Create .env with generated secrets, or generate the unset ones in an
# existing .env. Run it before the first `docker compose` call: Compose
# refuses to start any profile while a required secret is unset.
setup-env:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -f .env ]; then
        python3 scripts/env_secrets.py fill
    else
        python3 scripts/env_secrets.py create
    fi

# Format code (alias for `fmt`)
format: fmt

# Type-check with ty
ty:
    {{ uv }} run ty check .

# Run the whole suite without coverage (coverage runs in `just gauntlet`)
test-all:
    {{ uv }} run {{ test_extras }} pytest -q --no-cov

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

# A changed test file runs itself; a changed app file runs <app>/tests; with no
# mapped change, every test runs. Pass paths to choose them yourself.
# Fast loop: test the files changed since HEAD (no coverage, stop on failure)
test *paths:
    #!/usr/bin/env bash
    set -euo pipefail
    targets="{{ paths }}"
    if [ -z "$targets" ]; then
        targets=$({{ uv }} run python scripts/changed_tests.py)
        echo "Changed test targets: ${targets:-none, running the whole suite}"
    fi
    # shellcheck disable=SC2086 # targets is a space-separated path list
    {{ uv }} run {{ test_extras }} pytest -x -q --no-cov $targets

# Run the test suite with coverage
test-coverage:
    {{ uv }} run {{ test_extras }} pytest --cov=core --cov=todos --cov-report=term-missing

# Run the full suite against Postgres, then tear down.
# Host ports are offset from the defaults so this works while a local
# Postgres (5432) or Valkey (6379) is already running.
test-integration:
    #!/usr/bin/env bash
    set -euo pipefail
    pg_port="${TEST_POSTGRES_PORT:-5434}"
    valkey_port="${TEST_VALKEY_PORT:-6381}"
    trap 'POSTGRES_PORT=$pg_port VALKEY_PORT=$valkey_port {{ compose }} --profile test down' EXIT
    POSTGRES_PORT=$pg_port VALKEY_PORT=$valkey_port {{ compose }} --profile test up -d --wait {{ db_service }} valkey
    DB_HOST=127.0.0.1 DB_PORT=$pg_port CI=1 {{ uv }} run {{ test_extras }} pytest

# `uv run --with` layers Django 6.0 over the project environment in uv's cache,
# so .venv stays on the locked Django 5.2. Not a gate: DEPENDENCIES.md lists
# the Django 6 blockers. Set CI=1 to run on PostgreSQL instead of SQLite.
# Run the suite on Django 6.0 (manual check only)
test-django6 *args:
    {{ uv }} run {{ test_extras }} --with "Django~=6.0.0" python -c "import django; print('Django', django.get_version())"
    {{ uv }} run {{ test_extras }} --with "Django~=6.0.0" pytest -q --no-cov -p no:cacheprovider {{ args }}

# Run the Postgres-only tests (core.ai owner scoping, concurrent refresh) on a
# throwaway pgvector container. Also the AI-DB gauntlet gate; needs Docker.
test-ai-db *args:
    {{ uv }} run python scripts/test_ai_db.py {{ args }}

# Re-run tests whenever a Python file changes (polls, needs no extra tools)
test-watch:
    #!/usr/bin/env bash
    set -euo pipefail
    stamp=$(mktemp)
    trap 'rm -f "$stamp"' EXIT
    touch "$stamp"
    while true; do
        {{ uv }} run {{ test_extras }} pytest -x -q --no-cov || true
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

# Fail early when .env has no DJANGO_MCP_AUTH_TOKEN of 32+ characters. The
# container runs scripts/run_dev_mcp.py, which enforces the same rule.
_mcp-token:
    #!/usr/bin/env bash
    set -euo pipefail
    token=$(grep -E '^DJANGO_MCP_AUTH_TOKEN=' .env 2>/dev/null | tail -1 | cut -d= -f2- || true)
    if [ "${#token}" -lt 32 ]; then
        echo "Set DJANGO_MCP_AUTH_TOKEN (32+ characters) in .env: openssl rand -hex 32" >&2
        exit 1
    fi

# Start the django-ai-boost SSE server on 127.0.0.1:8001 (bearer token required)
mcp: _mcp-token
    {{ dev }} up -d --build mcp

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
# `--extra dev` installs the locked quality tools; plain `uv run` in a fresh
# clone would fall back to whatever ruff/mypy/bandit is on PATH.

# Lint with Ruff
lint:
    {{ uv }} run --extra dev ruff check .

# Lint and apply safe fixes
lint-fix:
    {{ uv }} run --extra dev ruff check . --fix

# Format with Ruff
fmt:
    {{ uv }} run --extra dev ruff format .

# Check formatting without writing
format-check:
    {{ uv }} run --extra dev ruff format --check .

# Type-check with mypy
typecheck:
    {{ uv }} run --extra dev mypy .

# Run the quick gauntlet (skips mutation testing and audit)
check-all:
    {{ uv }} run --extra dev python scripts/gauntlet.py --quick --verbose

# Run the quick gauntlet
gauntlet-quick:
    {{ uv }} run --extra dev python scripts/gauntlet.py --quick --verbose

# Run every gauntlet gate
gauntlet:
    {{ uv }} run --extra dev python scripts/gauntlet.py --verbose

# Run the gauntlet in CI mode with a JSON report
gauntlet-ci:
    {{ uv }} run --extra dev python scripts/gauntlet.py --ci --report

# Run one gauntlet gate (for example: just gauntlet-gate lint)
gauntlet-gate gate:
    {{ uv }} run --extra dev python scripts/gauntlet.py --gate {{ gate }} --verbose

# Check code conventions
check-conventions:
    {{ uv }} run python scripts/check_conventions.py

# Check cross-stack consistency
check-cross-stack:
    {{ uv }} run python scripts/check_cross_stack.py

# Check architecture constraints
check-arch:
    {{ uv }} run python scripts/check_architecture.py --all

# Export the OpenAPI contract to docs/openapi/openapi.json (sorted keys)
openapi:
    DJANGO_SETTINGS_MODULE=api.settings.test SECRET_KEY=openapi-export-not-a-secret {{ uv }} run python manage.py export_openapi

# Fail if docs/openapi/openapi.json is stale, then check schema parity
openapi-check:
    DJANGO_SETTINGS_MODULE=api.settings.test SECRET_KEY=openapi-export-not-a-secret {{ uv }} run python manage.py export_openapi --check
    {{ uv }} run python scripts/check_schema_parity.py

# Run mutation testing
mutation-test:
    {{ uv }} run --extra dev mutmut run

# Run the security scan
security-scan:
    {{ uv }} run --extra dev bandit -c pyproject.toml -r .

# Check that tool and service versions match across pyproject, Docker, hooks
check-drift:
    {{ uv }} run python scripts/check_version_drift.py

# Audit every locked package with pip-audit (blocking; see pip-audit-allowlist.toml)
audit:
    {{ uv }} run --extra dev python scripts/audit_dependencies.py

# Pinned versions for `just security-full`. semgrep_rules_ref is a commit of
# github.com/semgrep/semgrep-rules, so the ruleset only changes when you bump it.
semgrep_version := "1.179.0"
semgrep_rules_ref := "a84ff9cc2453ca91d581380de4b8b3f272f6f4be"
cyclonedx_version := "7.5.0"
trivy_version := "0.75.0"

# Optional deep scan, not a gauntlet gate: bandit, audit, semgrep, SBOM, trivy.
# Runs every step even when one fails, then fails if any step failed.
security-full:
    #!/usr/bin/env bash
    set -uo pipefail
    failed=()
    for step in security-scan audit semgrep sbom trivy; do
        echo "==> just $step"
        just "$step" || failed+=("$step")
    done
    if [ ${#failed[@]} -gt 0 ]; then
        echo "security-full: failed steps: ${failed[*]}" >&2
        exit 1
    fi
    echo "security-full: every step passed"

# Scan with semgrep using the pinned semgrep-rules commit (Django, JWT, security)
semgrep:
    #!/usr/bin/env bash
    set -euo pipefail
    rules="${XDG_CACHE_HOME:-$HOME/.cache}/django-ninja-boilerplate/semgrep-rules-{{ semgrep_rules_ref }}"
    if [ ! -d "$rules/.git" ]; then
        git init -q "$rules"
        git -C "$rules" fetch -q --depth 1 https://github.com/semgrep/semgrep-rules.git {{ semgrep_rules_ref }}
        git -C "$rules" checkout -q FETCH_HEAD
    fi
    uvx semgrep=={{ semgrep_version }} scan --metrics=off --error \
        --config "$rules/python/django" \
        --config "$rules/python/lang/security" \
        --config "$rules/python/jwt" .

# Write a CycloneDX SBOM of every locked package to build/sbom.cdx.json
sbom:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p build
    requirements=$(mktemp)
    trap 'rm -f "$requirements"' EXIT
    {{ uv }} export --frozen --all-extras --no-emit-project --quiet --output-file "$requirements"
    uvx --from cyclonedx-bom=={{ cyclonedx_version }} cyclonedx-py requirements "$requirements" \
        --output-format JSON --output-file build/sbom.cdx.json
    echo "Wrote build/sbom.cdx.json"

# Build the production image on a freshly pulled base and scan it with trivy
# (HIGH/CRITICAL with a fix available fail)
trivy:
    docker build --pull --target production --build-arg APP_VERSION --build-arg UV_EXTRAS --tag django-ninja-boilerplate:scan .
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$HOME/.cache/trivy:/root/.cache/trivy" aquasec/trivy:{{ trivy_version }} \
        image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed django-ninja-boilerplate:scan

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

# Configure through the CLI, then build and prepare the selected stack
setup +args:
    {{ uv }} run --project cli dnm setup {{ args }}

# Non-interactive setup stages called by `dnm setup`
setup-services:
    python3 scripts/env_secrets.py fill
    ./scripts/doctor.sh
    # --wait keeps `just migrate` from racing the container's own migrate.
    just _stack up -d --build --wait
    just migrate
    just create-superuser
    just wait-for-api

# Wait until the API answers its health check
wait-for-api:
    #!/usr/bin/env bash
    set -euo pipefail
    port="$(
        {{ uv }} run --project cli python -c \
            'from pathlib import Path; from django_ninja_matt.commands.setup import read_environment_value; print(read_environment_value(Path(".env"), "DJANGO_PORT", "8000"))'
    )"
    for _ in $(seq 1 60); do
        if curl -fsS "http://localhost:${port}/api/health/" >/dev/null 2>&1; then
            echo "API is up: http://localhost:${port}/api/docs"
            exit 0
        fi
        sleep 1
    done
    echo "The API did not answer /api/health/ on port ${port} within 60s." >&2
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

# Bump the version, commit, and tag locally. Pass a version and --push to
# publish, for example: just release 1.12.0 --push
release *args:
    {{ uv }} run python scripts/release.py {{ args }}

# Preview the version bump without writing anything (optional X.Y.Z version)
release-dry-run *args:
    {{ uv }} run python scripts/release.py --dry-run {{ args }}

# Check deployment status for the configured provider
deploy-status:
    ./scripts/deploy.sh --status

# Tail deployment logs for the configured provider
deploy-logs:
    ./scripts/deploy.sh --logs

# Roll back to the previous deployment
deploy-rollback:
    ./scripts/deploy.sh --rollback
