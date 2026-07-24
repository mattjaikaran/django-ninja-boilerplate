# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.8.0] - 2026-07-24

### Added
- **Constraint Tools Philosophy** — formalized the approach inspired by [Uncle Bob Martin's SwarmForge](https://github.com/unclebob/swarm-forge): agents write the deterministic tools that check constraints. Small programs, binary pass/fail, no human judgment required. If code survives all constraint tools, you don't need to read it. Documented in `docs/CONSTRAINT_TOOLS.md` and `CLAUDE.md`.
- **The Gauntlet** — 10-gate quality pipeline implementing the constraint tools philosophy. Every code change must survive all gates before merge:
  1. FORMAT (ruff format --check)
  2. LINT (ruff check — 50+ rule categories)
  3. TYPECHECK (mypy)
  4. SECURITY (bandit)
  5. ARCHITECTURE (layer enforcement)
  6. FILELENGTH (max 400 lines)
  7. TEST (pytest --cov-fail-under=35)
  8. MUTATION (mutmut — test quality validation)
  9. AUDIT (pip-audit — dependency vulnerabilities)
  10. DEPLOY (manage.py check --deploy)
- **Architecture enforcement** (`scripts/check_architecture.py`) — validates Controllers → Services → Models layering, prevents cross-app controller coupling, detects reverse dependencies. Works in both standalone and mattstack-scaffolded layouts.
- **Gauntlet orchestrator** (`scripts/gauntlet.py`) — runs all gates with `--quick`, `--ci`, `--fail-fast`, `--gate`, `--report` modes. Generates JSON reports for CI artifact upload.
- **Mutation testing** via `mutmut` — validates that tests actually catch bugs, not just execute code paths.
- **Makefile targets**: `gauntlet`, `gauntlet-quick`, `gauntlet-ci`, `gauntlet-gate`, `check-arch`, `mutation-test`, `mutation-results`, `security-scan`, `check-file-length`
- **CI gauntlet job** — architecture check, file length check, and full gauntlet run as a GitHub Actions job with artifact upload
- **Pre-commit architecture hook** — validates layer constraints on every commit
- **Commitizen commit-msg hook** — enforces conventional commit format
- **Constraint tool template** — documented pattern for writing new gates: deterministic, <400 lines, binary pass/fail, agent-writable. See `docs/CONSTRAINT_TOOLS.md`.

### Changed
- **Coverage threshold** raised from 25% to 35% (ratchet toward 80%) — every PR must maintain or increase coverage
- **VS Code settings** migrated from deprecated ruff-lsp to native Ruff extension (`ruff.nativeServer: "on"`, removed `ruff.showNotifications`)
- **Security scanning** in CI is now mandatory (bandit runs as a blocking gate, not `|| true`)
- **CLAUDE.md** expanded with gauntlet documentation, Definition of Done checklist, architecture rules, and mattstack-cli integration notes
- **`check-all` Makefile target** now delegates to `gauntlet --quick` instead of individual commands

### Dependencies
- Added (dev): `mutmut>=3.2.0`, `bandit[toml]>=1.8.0`, `commitizen>=4.1.0`

## [1.7.0] - 2026-07-04

### Changed
- **CLAUDE.md rewritten** — slim, Karpathy-inspired behavioral guidelines with 5 principles (ask don't assume, match complexity, surgical changes, flag uncertainty, suggest better approaches)
- **Version strings synced** — `pyproject.toml`, `api/settings/common.py`, and `Makefile` all report `1.7.0` (were drifted at `1.2.0` in settings/Makefile)
- **Consolidated env files** — removed duplicate `env.example`, canonical file is `.env.example` with all env vars documented (Valkey, task backends, API keys, JWT, email, Centrifugo, Stripe, OAuth)
- **Pre-commit ruff version** — bumped `v0.13.2` → `v0.15.10` to match `pyproject.toml`
- **Ruff isort known-first-party** — added all Django apps (billing, files, webhooks, organizations, notifications)
- **Hatch wheel packages** — added all satellite apps to `[tool.hatch.build.targets.wheel]`
- **Makefile cleanup:**
  - Fixed `install`/`sync`/`install-dev` to use `uv sync` instead of `uv pip install/sync`
  - Deduplicated `health`, `celery-worker`, `db-restore` targets (renamed duplicates to `local-*` and `db-restore-mgmt`)
  - Removed stale `env.example` fallback from `setup-env`
  - Added `typecheck`, `check-all`, `up-observability` targets
  - Synced version display to `v1.7.0`
- **Production settings fixes:**
  - Removed invalid `MAX_CONNS`/`MIN_CONNS` DB options (pgbouncer-only), added `CONN_HEALTH_CHECKS`
  - Fixed CSP to use django-csp 4.x `CONTENT_SECURITY_POLICY` dict format (was using legacy `CSP_*` vars)
- **Dev settings cleanup** — removed dead commented-out code (SQLite fallback, debug toolbar INSTALLED_APPS, django-extensions), removed orphaned `RUNSERVER_PLUS_PRINT_SQL`
- **Docker Compose** — added `VALKEY_URL` to celery-worker and celery-beat services, fixed header comment (`redis` → `valkey`)
- **Module exports** — `core/schemas/__init__.py` now exports API key schemas, `core/security/__init__.py` exports `APIKeyAuth`

## [1.6.0] - 2026-07-04

### Added
- **Valkey as default cache/broker** — wire-compatible Redis fork (BSD license) using `valkey/valkey:8-alpine` Docker image. Configurable via `CACHE_BACKEND` env var with three options:
  - `vcache` (default) — django-vcache with Rust I/O driver for maximum performance
  - `valkey` — django-valkey, stable fork of django-redis
  - `redis` — original django-redis backend for backward compatibility
- **API Key authentication** — built-in machine-to-machine auth via `X-API-Key` header
  - `APIKey` model with prefix-based lookup and SHA-256 hashed secrets
  - Scoped permissions (e.g., `read:todos`, `write:todos`)
  - Key rotation, revocation, and expiry support
  - CRUD endpoints at `/api/api-keys/` (JWT-protected)
  - Django admin integration via Unfold
- **Global orjson renderer** — 2-10x faster JSON serialization for all API responses
  - `ORJSONRenderer` and `ORJSONParser` for Django Ninja
  - Native datetime, UUID, dataclass, and numpy handling
- **Pluggable task queue backends** — `TASK_BACKEND` env var with full parallel support:
  - Celery (default, unchanged)
  - Huey (`uv sync --extra huey`)
  - django-q2 (`uv sync --extra django-q`)
  - django-rq (`uv sync --extra django-rq`)
  - Abstraction layer: `from api.tasks import shared_task`
  - Docker Compose profiles for each backend
- **ty type checker** — Astral's Rust-based type checker alongside mypy (`make ty`)
- **New documentation:**
  - `docs/TASK_BACKENDS.md` — comparison and setup guide for all task queue options
  - `docs/API_KEYS.md` — API key auth guide with usage examples
  - `docs/MIGRATION.md` — step-by-step migration guide for existing codebases

### Changed
- Docker Compose services renamed: `redis` → `valkey` (volumes: `redis_data` → `valkey_data`)
- `VALKEY_URL` is the new canonical env var (`REDIS_URL` kept as fallback alias)
- Celery broker/result URLs default to `VALKEY_URL` instead of `REDIS_URL`
- Makefile: new `valkey-*` targets, `redis-*` kept as aliases
- Railway deployment config updated for Valkey template

### Dependencies
- Added: `django-valkey>=0.4.1`, `django-vcache>=0.1.0`
- Added (optional): `huey>=2.5.0`, `django-q2>=1.7.0`, `django-rq>=2.10.0`, `rq>=1.16.0`
- Added (dev): `ty>=0.0.1a1`

## [1.5.1] - 2026-04-14

### Added
- **Reusable HTTP client** (`api/utils/http_client.py`) — async/sync wrapper around httpx
  - Pydantic `response_model` for automatic response parsing via `TypeAdapter`
  - Configurable retries, timeouts, and expected status code validation
  - `HttpClientError` with status code and response body for structured error handling
  - Module-level `http_client` singleton for zero-config usage
- **Granian migration prompt template** — step-by-step guide in `.context/PROMPTS.md` for swapping Gunicorn to Granian (Rust-based WSGI/ASGI server), covering Dockerfile, docker-compose, k8s, PaaS, logging, and optional ASGI mode
- **Mermaid diagram upgrades** — converted all ASCII box diagrams in `docs/ARCHITECTURE.md` and `docs/REALTIME.md` to Mermaid for native GitHub rendering

### Changed
- **Bumped all dependencies to latest versions**
  - Django ecosystem: django-environ 0.13.0, cors-headers 4.7.0, debug-toolbar 5.2.0, flags 5.0.14, import-export 4.3.7, js-asset 3.1.0, storages 1.14.6, unfold 0.52.0, ninja-extra 0.31.3, ninja-jwt 5.4.3, celery 5.5.2, celery-beat 2.7.0
  - Infrastructure: redis 7.4.0, flower 2.0.1, httpcore 1.0.9, uvloop 0.22.1, gunicorn 25.3.0, python-dotenv 1.2.2, charset-normalizer 3.4.7
  - Dev/testing: ruff 0.15.10, pytest 9.0.3, pytest-django 4.12.0, pytest-cov 6.2.1, pytest-mock 3.14.0, factory-boy 3.3.3
  - CLI deps: typer 0.24.1, rich 15.0.0, jinja2 3.1.6, pyyaml 6.0.3, questionary 2.1.1
  - CI actions: codecov/codecov-action v5→v6, softprops/action-gh-release v2→v3

### Removed
- **`requests`** — completely unused; httpx covers all HTTP client needs
- **`uvicorn`** — project uses WSGI (Gunicorn), not ASGI
- **`click`** — transitive dependency via Celery, no direct usage
- **`rich`** (root) — only used in CLI package, which declares its own copy

## [1.5.0] - 2026-03-30

### Added
- **Pydantic camelCase aliases** — automatic snake_case ↔ camelCase conversion for API schemas
  - `AliasPath` support for nested field access
  - `populate_by_name=True` for dual snake_case/camelCase input acceptance
- **Comprehensive LLM prompt templates** — framework-aware code generation prompts in `.context/`

## [1.4.0] - 2026-03-20

### Added
- **K3s deployment support** — lightweight Kubernetes deployment using plain YAML manifests
  - `deploy/k3s/namespace.yaml` — dedicated namespace
  - `deploy/k3s/secrets.yaml` — centralized secrets management with fail-safe placeholders
  - `deploy/k3s/configmap.yaml` — application configuration
  - `deploy/k3s/postgres.yaml` — PostgreSQL with local-path PVC (k3s default storage)
  - `deploy/k3s/redis.yaml` — Redis with password authentication and persistence
  - `deploy/k3s/django.yaml` — Django deployment (2 replicas) with init container migrations
  - `deploy/k3s/celery.yaml` — Celery worker and beat deployments
  - `deploy/k3s/ingress.yaml` — Traefik ingress (k3s built-in) with rate limiting middleware
  - `deploy/k3s/README.md` — full deployment guide with k3s vs k8s comparison
- **Nginx security headers** — HSTS with preload, `Permissions-Policy`, `X-Permitted-Cross-Domain-Policies`

### Changed
- **Hardened rate limits** — login and token verification endpoints increased from 10 to 20 req/min for better UX while maintaining brute-force protection
- **Tightened Content-Security-Policy** — removed `unsafe-inline`, `http:`, `blob:`; restricted `default-src` to `'self'`
- **Updated `X-XSS-Protection`** — changed from `1; mode=block` to `0` per modern best practice (CSP replaces it)
- **Stricter `Referrer-Policy`** — changed from `no-referrer-when-downgrade` to `strict-origin-when-cross-origin`

### Security
- **Fixed shell injection in `docker-entrypoint.sh`** — replaced inline Python heredoc (which interpolated env vars directly into code) with the safe `create_superuser` management command
- **Removed hardcoded fallback secrets from `docker-compose.yml`** — `SECRET_KEY`, `CENTRIFUGO_API_KEY`, `CENTRIFUGO_TOKEN_SECRET`, and `FLOWER_BASIC_AUTH` now use `${VAR:?must be set}` syntax that fails fast if env vars are missing, instead of falling back to guessable defaults like `admin:admin`

## [1.3.0] - 2026-02-26

### Added
- **Four progressive Todo controller patterns** — declarative, basic, partial, and full service-layer
  - `todos/controllers/todo_controller_declarative.py` — explicit `try/except`, no decorator magic
  - `todos/controllers/todo_controller_basic.py` — minimal, `get_object_or_404`, no custom decorators
  - `todos/controllers/todo_controller_partial.py` — `@handle_exceptions` + `@log_api_call` on writes only
  - `todos/controllers/todo_controller.py` — full decorator stack + injected `TodoService`
- **TodoService** (`todos/services/todo_service.py`) — extracted all business logic from the controller into a dedicated, testable service layer
- **Resend email backend integration** — `django-anymail[resend]` as default mailer with console fallback
- **Smoke test suite** — lightweight tests verifying all 4 controller route prefixes are reachable
- **Google-style docstrings** across all controllers and services
- **CLI `--docstrings` flag** — generated projects include Google-style docstrings by default
- **CLI `--email-backend` flag** — select email backend (Resend, console, SMTP) during project generation
- **Centrifugo Real-Time Messaging** — standalone WebSocket server replacing Django Channels
  - `api/centrifugo.py` — JWT token generation and HTTP client for publishing
  - Token endpoints: `POST /api/realtime/connection-token` and `/subscription-token`
  - Centrifugo server config with chat, notifications, and organization namespaces
  - Docker Compose service under `realtime` profile (port 8800)
  - Nginx WebSocket proxy at `/centrifugo/`
  - `make up-realtime` command
  - Full documentation at `docs/REALTIME.md`
  - 15 unit tests for token generation and client methods
- **`todos/README.md`** — dedicated docs for the todos example app with pattern table and code examples
- **`docs/ARCHITECTURE.md` — Progressive Controller Patterns section** with ASCII diagram, pattern comparison, and decorator stack diagram

### Changed
- `TodoController` now delegates all operations to an injected `TodoService`; controller methods are one-liners
- Bandit security scan moved to pre-push hook (was blocking commits on every save)
- Replaced Django Channels consumer templates with Centrifugo service templates in code generators
- Removed `channels` and `channels-redis` dependencies from chat and notification generators
- Updated notification generator `_send_in_app` to publish via Centrifugo
- Updated `make up-full` and `make down-full` to include `--profile realtime`

## [1.2.0] - 2026-02-17

### Added
- **Test settings module** (`api/settings/test.py`) - SQLite locally, PostgreSQL in CI
- **Resend email integration** (`django-anymail[resend]`) - Default mailer with console fallback
- **CLI `add-app` command** - Scaffold new Django apps with model/controller/schema/test stubs
- Missing migration for `deleted_at` and `deleted_by` fields on Todo model
- `ordering = ["-created_at"]` on Todo model Meta

### Changed
- Updated minimum Python version from 3.12 to **3.13** (supports 3.13 and 3.14)
- Updated default Python version in CI from 3.14 to **3.13**
- Updated CI test matrix to Python 3.13 + 3.14 (dropped 3.12)
- Updated Dockerfile base image from `python:3.14-slim` to `python:3.13-slim`
- Updated ruff target version from `py312` to `py313`
- Updated CLI tool to v1.2.0 with enhanced version output
- Updated CLI `test` command to set `DJANGO_SETTINGS_MODULE=api.settings.test`
- Updated UV version in CI from 0.5.0 to 0.6.0
- Updated pytest to use `DJANGO_SETTINGS_MODULE=api.settings.test`
- Updated pre-commit default Python from 3.14 to 3.13
- Updated all `pip install` references to `uv add`
- Updated all documentation to reflect Python 3.13+ requirement

### Fixed
- Fixed test suite to run locally without PostgreSQL (SQLite fallback)
- Fixed `test_signup` test URL from `/api/users/signup` to `/api/auth/signup`
- Fixed Todo model missing `deleted_at`/`deleted_by` migration (schema mismatch)
- Fixed Todo model ordering (was unspecified, now `-created_at`)
- Fixed CLI `lint` command dead code in formatter branch
- All 26 tests now pass locally and in CI

## [1.1.0] - 2026-02-05

### Added
- **Audit Logging System** - Comprehensive compliance tracking (GDPR, SOC2, HIPAA ready)
  - Automatic model change tracking via Django signals
  - API request/response logging middleware
  - Authentication event tracking (login, logout, failures)
  - Immutable audit trail with preserved user emails
  - Admin interface for viewing and filtering logs
  - REST API endpoints for audit log queries

- **Feature Flags System** - Gradual rollouts and A/B testing
  - Boolean, percentage-based, and A/B test flag types
  - User and environment targeting
  - Time-based activation windows
  - Middleware for automatic flag attachment to requests
  - Admin panel management with bulk actions
  - REST API for flag management and evaluation

- **Observability Stack** - Production monitoring
  - OpenTelemetry distributed tracing with Jaeger integration
  - Prometheus metrics endpoint (`/api/metrics`)
  - Structured JSON logging with trace context
  - Enhanced health checks with component status
  - Request timing and slow request logging
  - Docker Compose profile for observability services

- **Task Management Improvements** - Enhanced Celery task handling
  - Progress tracking with `ProgressTask` base class
  - Dead Letter Queue (DLQ) for failed tasks
  - Periodic task scheduling API
  - Task status and progress REST endpoints
  - `TaskResult` model for persistent task tracking
  - Bulk retry and resolution for failed tasks

- **Testing Utilities** - Comprehensive testing toolkit
  - Contract tests with Schemathesis for OpenAPI validation
  - Load tests with Locust for performance testing
  - Enhanced test client with auth helpers
  - Custom assertions for API responses
  - Factory utilities for test data generation

- **OpenAPI Enhancements** - SDK generation and API tools
  - TypeScript SDK generator
  - Python SDK generator
  - Postman collection export
  - Insomnia collection export
  - API changelog generator for version comparison
  - OpenAPI spec validation

- **GraphQL Generator** - Optional Strawberry GraphQL setup
  - Management command to scaffold GraphQL for any app
  - JWT-authenticated GraphQL endpoint
  - Query and mutation types with examples
  - Custom context class with user access

### Changed
- Updated Python requirement to 3.13+ (from 3.11+)
- Updated all Dockerfiles to Python 3.13-slim
- Updated CI actions to latest versions (checkout@v6, setup-python@v6, setup-uv@v7)
- Consolidated `get_client_ip` utility to single canonical source
- Split pagination module into subpackage (`api/pagination/`)
- Split throttling module into subpackage (`api/throttling/`)
- Added `OffsetPaginator` and `TokenBucketRateLimiter` aliases for clarity

### Removed
- Legacy `todo_controller_legacy.py`
- Unused flake8 and isort configuration files (Ruff handles all linting)

## [1.0.0] - 2026-01-26

### Added
- **Developer Experience (DX) Overhaul**
  - One-command setup: `make setup` for complete project bootstrap
  - Environment doctor: `make doctor` validates Python, Docker, ports, and config
  - Docker Compose profiles for flexible service management:
    - `make up` - Core services (db, redis, django)
    - `make up-celery` - With Celery worker and beat
    - `make up-monitoring` - With Flower dashboard
    - `make up-full` - All services
  - `.env.development` with sensible defaults (committed)
  - `.dockerignore` for optimized Docker builds
  - VSCode configurations (settings, launch, tasks, extensions)
  - VERSION file for semantic versioning
  - CHANGELOG.md following Keep a Changelog format

- **CLI Tool (`django-ninja-matt`)**
  - Interactive project scaffolding with Typer + Rich
  - Commands: `dnm init`, `dnm doctor`, `dnm setup`
  - Standalone API and Monorepo project types
  - Feature selection (Celery, Redis, auth methods)
  - Deployment target configuration

- **Deployment Configurations**
  - Single-container Dockerfile for PaaS (`deploy/docker/Dockerfile.single`)
  - Railway configuration (`deploy/paas/railway.json`, `railway.toml`)
  - Render Blueprint (`deploy/paas/render.yaml`)
  - Kubernetes Helm chart with:
    - Backend deployment with health checks
    - Celery worker deployment
    - Celery beat deployment
    - Flower monitoring deployment
    - PostgreSQL and Redis subcharts
  - `docker-compose.single.yml` for single-container local testing

- **CI/CD**
  - GitHub Actions workflow for lint, test, Docker build
  - Security scanning with pip-audit
  - Automated releases workflow
  - Dependabot configuration for dependency updates

- **Infrastructure**
  - Celery worker and beat services in Docker Compose (profile-based)
  - Flower monitoring service (profile-based)

### Changed
- Enhanced `scripts/setup.sh` with `--auto` mode for CI/CD
- Improved Makefile with profile-based commands
- Updated docker-compose.yml with service profiles

## [0.8.0] - 2026-01-25

### Added
- OTP (One-Time Password) authentication support
- New user model fields including metadata
- Base model, service, and schema patterns
- SQL dump/restore commands
- Rate limiting middleware
- New make commands for data management

### Changed
- Updated user model with enhanced fields
- Improved authentication decorators

## [0.7.0] - 2026-01-20

### Added
- Django Ninja JWT authentication
- Custom user model with email-based auth
- Todo app as example CRUD implementation
- Comprehensive API documentation (Swagger/ReDoc)
- Health check endpoint
- Docker development environment with hot reload
- PostgreSQL 17 and Redis 7.2 services
- UV package management integration
- Ruff linting and formatting
- pytest test suite with coverage
- Pre-commit hooks configuration

### Changed
- Migrated from pip to UV for package management

## [0.6.0] - 2026-01-15

### Added
- Initial Django 5.2 + Django Ninja setup
- Basic project structure
- Docker Compose configuration
- Makefile for common operations

---

## Version History Summary

| Version | Date | Description |
|---------|------|-------------|
| 1.8.0 | 2026-07-24 | The Gauntlet, constraint tools, mutation testing, architecture enforcement |
| 1.7.0 | 2026-07-04 | CLAUDE.md rewrite, version sync, env consolidation, Makefile cleanup |
| 1.6.0 | 2026-07-04 | Valkey, API keys, orjson, pluggable task queues, ty type checker |
| 1.5.1 | 2026-04-14 | Dep cleanup, HTTP client, Mermaid diagrams, granian prompt |
| 1.5.0 | 2026-03-30 | Pydantic camelCase aliases, LLM prompt templates |
| 1.4.0 | 2026-03-20 | K3s deployment, security hardening, nginx headers |
| 1.3.0 | 2026-02-26 | 4 controller patterns, TodoService, Resend, Centrifugo real-time |
| 1.2.0 | 2026-02-17 | Python 3.13+ default, test fixes, migration fixes |
| 1.1.0 | 2026-02-05 | Audit logging, feature flags, observability, task management |
| 1.0.0 | 2026-01-26 | DX Overhaul, CLI tool, K8s Helm chart |
| 0.8.0 | 2026-01-25 | OTP, enhanced user model, rate limiting |
| 0.7.0 | 2026-01-20 | JWT auth, UV, Docker dev environment |
| 0.6.0 | 2026-01-15 | Initial release |

[Unreleased]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.8.0...HEAD
[1.8.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.5.1...v1.6.0
[1.5.1]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.8.0...v1.0.0
[0.8.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/releases/tag/v0.6.0
