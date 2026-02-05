# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- Updated Python requirement to 3.12+ (from 3.11+)
- Updated all Dockerfiles to Python 3.14-slim
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
| 1.1.0 | 2026-02-05 | Audit logging, feature flags, observability, task management |
| 1.0.0 | 2026-01-26 | DX Overhaul, CLI tool, K8s Helm chart |
| 0.8.0 | 2026-01-25 | OTP, enhanced user model, rate limiting |
| 0.7.0 | 2026-01-20 | JWT auth, UV, Docker dev environment |
| 0.6.0 | 2026-01-15 | Initial release |

[Unreleased]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.8.0...v1.0.0
[0.8.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mattjaikaran/django-ninja-boilerplate/releases/tag/v0.6.0
