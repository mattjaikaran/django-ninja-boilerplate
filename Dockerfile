# Django Ninja Boilerplate - Unified Multi-Stage Dockerfile
# ============================================================
# This Dockerfile uses multi-stage builds with named targets that can be
# selected via the --target flag, so there is one Dockerfile for every
# environment (deploy/docker/Dockerfile.single is the PaaS image).
#
# Available targets:
#   - base:        Common base with system dependencies (internal use)
#   - builder:     Build stage with uv and compilation (internal use)
#   - development: Dev stage with hot reload, debug tools
#   - production:  Optimized production stage (DEFAULT)
#   - ci:          Minimal stage for CI/CD testing
#
# Usage examples:
#   docker build -t myapp .                           # builds production (default)
#   docker build -t myapp --target development .      # builds development
#   docker build -t myapp --target ci .               # builds ci
#   docker build -t myapp --target production .       # explicitly builds production
#
# ============================================================

# Python base image, pinned for every stage. Bump PYTHON_VERSION and
# PYTHON_IMAGE_DIGEST together (`docker buildx imagetools inspect
# python:<version>-slim-trixie`), in this file and in
# deploy/docker/Dockerfile.single; scripts/check_version_drift.py compares them
# with pyproject.toml requires-python.
ARG PYTHON_VERSION=3.13.15
ARG PYTHON_IMAGE_DIGEST=sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b

# ===========================================
# Stage 1: BASE - Common system dependencies
# ===========================================
# This stage sets up the foundational system packages and environment
# variables that are shared across all other stages.
FROM python:${PYTHON_VERSION}-slim-trixie@${PYTHON_IMAGE_DIGEST} AS base

# Metadata labels. APP_VERSION comes from the VERSION file: the justfile
# exports it and Compose passes it as a build arg. A bare `docker build`
# without --build-arg APP_VERSION labels the image "unknown".
ARG APP_VERSION=unknown
LABEL maintainer="Matt Jaikaran <info@mattjaikaran.com>" \
      description="Django Ninja API Boilerplate" \
      org.opencontainers.image.title="django-ninja-boilerplate" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/mattjaikaran/django-ninja-boilerplate"

# Common environment variables for all stages
# These optimize Python's behavior in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    # Application defaults
    DJANGO_SETTINGS_MODULE=api.settings \
    PORT=8000 \
    # Virtual environment location
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install common runtime dependencies needed by all stages. psycopg[binary]
# bundles libpq, so the image needs no system libpq. `apt-get upgrade` pulls
# Debian security fixes (for example openssl) that the base tag lags behind.
# - curl: HTTP client for health checks
# - netcat-openbsd: Network utility for service readiness checks
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        curl \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/*


# ===========================================
# Stage 2: BUILDER - Dependency compilation
# ===========================================
# This stage installs build tools and compiles Python dependencies.
# It creates a virtual environment that will be copied to runtime stages.
FROM base AS builder

# Build-time environment variables
# UV_COMPILE_BYTECODE: Pre-compile Python files for faster startup
# UV_LINK_MODE: Use copy mode for cleaner venv isolation
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies (these won't be in final runtime images)
# - build-essential: C compiler for any dependency without a wheel
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# uv, pinned. Keep this tag equal in deploy/docker/Dockerfile.single;
# scripts/check_version_drift.py compares them.
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /bin/

# Optional extras, space-separated (for example UV_EXTRAS="sentry ai"). Compose
# and the justfile pass UV_EXTRAS through; each name becomes `--extra <name>`.
ARG UV_EXTRAS=""

# Copy only dependency files first for better layer caching
# Changes to application code won't invalidate dependency cache
COPY pyproject.toml uv.lock* README.md LICENSE ./

# Install production dependencies from the lock so the image matches uv.lock
# instead of resolving fresh (a fresh resolve can pick a different Django).
# Every task backend is installed so TASK_BACKEND can be switched without a
# rebuild: celery is in the base dependencies, the rest are extras. The
# observability extra lets OTEL_ENABLED=true export traces without a rebuild.
# Both sync steps take the same flags: `uv sync` removes anything the flags
# do not select, so a mismatch would drop packages in the second step.
RUN extras=""; for name in ${UV_EXTRAS}; do extras="${extras} --extra ${name}"; done \
    && UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --locked --no-dev \
    --extra huey --extra django-q --extra django-rq --extra dramatiq \
    --extra observability ${extras} \
    --no-install-project

# Install the project itself as a regular (non-editable) package. The source
# is needed to build it; only /opt/venv leaves this stage.
COPY . .
RUN extras=""; for name in ${UV_EXTRAS}; do extras="${extras} --extra ${name}"; done \
    && UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --locked --no-dev \
    --extra huey --extra django-q --extra django-rq --extra dramatiq \
    --extra observability ${extras} \
    --no-editable


# ===========================================
# Stage 3: DEVELOPMENT - Dev environment
# ===========================================
# This stage is optimized for local development with:
# - Hot reload support
# - Debug tools and dev dependencies
# - Source code mounted as volume
FROM base AS development

# Development-specific environment
ENV DEBUG=1 \
    PYTHONDEBUG=1

# Install development-specific system tools
# - git: Version control for pre-commit hooks
# - procps: Process utilities (ps, top) for debugging
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy the pinned uv from builder for installing dev dependencies
COPY --from=builder /bin/uv /usr/local/bin/uv

# Install dev dependencies from the lock (reproducible), then the project.
# The same UV_EXTRAS as the builder, so this sync keeps those packages.
ARG UV_EXTRAS=""
COPY pyproject.toml uv.lock* README.md LICENSE ./
RUN extras=""; for name in ${UV_EXTRAS}; do extras="${extras} --extra ${name}"; done \
    && UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --locked --extra dev \
    --extra huey --extra django-q --extra django-rq --extra dramatiq \
    --extra observability ${extras} \
    --no-install-project
RUN uv pip install --no-cache --no-deps -e .

# Create non-root user for security (even in development)
RUN useradd --create-home --shell /bin/bash --uid 1000 app \
    && mkdir -p /app/logs /app/staticfiles /app/media \
    && chown -R app:app /app /opt/venv

# Copy application code (will be overridden by volume mount in docker-compose)
COPY --chown=app:app . .

# Copy and set permissions for the development entrypoint. The shared
# docker-entrypoint.sh is used by deploy/docker/Dockerfile.single; the
# production stack runs migrations from its compose command.
COPY --chown=app:app docker-entrypoint-dev.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint-dev.sh

# Switch to non-root user
USER app

# Expose port
EXPOSE 8000

# Health check for development
# More lenient timing for development environment
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ["curl", "-f", "http://localhost:8000/api/health/"]

# Default command - Django development server with hot reload
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


# ===========================================
# Stage 4: PRODUCTION - Optimized runtime
# ===========================================
# This stage creates the smallest possible production image with:
# - Only runtime dependencies
# - Non-root user for security
# - Gunicorn with uvicorn ASGI workers (settings in gunicorn.conf.py)
# - Pre-compiled static files
FROM base AS production

# Production-specific environment
# PYTHONOPTIMIZE=1 strips asserts only. Level 2 would also strip docstrings,
# which Django Ninja reads for OpenAPI operation descriptions.
# The base stage defaults DJANGO_SETTINGS_MODULE to the bare "api.settings",
# which the settings selector resolves to dev. Pin production explicitly so the
# image is correct even without compose-supplied environment.
# USE_TLS=true: api.settings.prod refuses to start without TLS in front.
ENV PYTHONOPTIMIZE=1 \
    DJANGO_SETTINGS_MODULE=api.settings.prod \
    ENVIRONMENT=production \
    USE_TLS=true

# Copy virtual environment from builder (no dev dependencies)
COPY --from=builder /opt/venv /opt/venv

# Create non-root user for security. Remove the base image's pip: uv does
# every install, and pip's vendored msgpack, urllib3 and setuptools carry
# advisories that trivy reports. Call the system Python: PATH puts the
# pip-less /opt/venv first.
RUN /usr/local/bin/python -m pip uninstall -y pip \
    && useradd --create-home --shell /bin/bash --uid 1000 app \
    && mkdir -p /app/logs /app/staticfiles /app/media \
    && chown -R app:app /app

# Copy application code
COPY --chown=app:app . .

# Copy and set permissions for the development entrypoint. The shared
# docker-entrypoint.sh is used by deploy/docker/Dockerfile.single; this stack
# runs migrations from its compose command.
COPY --chown=app:app docker-entrypoint-dev.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint-dev.sh

# Switch to non-root user
USER app

# Collect static files at build time. Importing settings needs these env vars;
# placeholders are passed inline so they are not baked into the image, and the
# real values are injected at runtime.
RUN SECRET_KEY=build-time-placeholder \
    NINJA_JWT_SIGNING_KEY=build-time-jwt-placeholder \
    CENTRIFUGO_TOKEN_SECRET=build-time-placeholder \
    CENTRIFUGO_API_KEY=build-time-placeholder \
    DJANGO_SETTINGS_MODULE=api.settings.prod USE_TLS=true \
    DB_NAME=build DB_USER=build DB_PASSWORD=build DB_HOST=build DB_PORT=5432 \
    python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Production health check. Gunicorn binds $PORT (gunicorn.conf.py), so probe
# the same port.
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health/" || exit 1

# Gunicorn manages the processes; each worker serves ASGI through uvicorn.
# gunicorn.conf.py (loaded from /app) sets the worker class, bind address,
# timeouts and recycling. Tune it with GUNICORN_WORKERS, GUNICORN_TIMEOUT and
# the DB_POOL_* variables.
CMD ["gunicorn", "api.asgi:application"]


# ===========================================
# Stage 5: CI - Minimal testing environment
# ===========================================
# This stage is optimized for CI/CD pipelines with:
# - Minimal footprint for fast image pulls
# - Test dependencies included
# - No static file collection
# - No health check (not needed in CI)
FROM base AS ci

# CI-specific environment
ENV CI=1 \
    TESTING=1

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy the pinned uv from builder for installing test dependencies
COPY --from=builder /bin/uv /usr/local/bin/uv

# Install test/dev dependencies from the lock (reproducible), then the project.
# The same UV_EXTRAS as the builder, so this sync keeps those packages.
ARG UV_EXTRAS=""
COPY pyproject.toml uv.lock* README.md LICENSE ./
RUN extras=""; for name in ${UV_EXTRAS}; do extras="${extras} --extra ${name}"; done \
    && UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --locked --extra dev \
    --extra huey --extra django-q --extra django-rq --extra dramatiq \
    --extra observability ${extras} \
    --no-install-project
RUN uv pip install --no-cache --no-deps -e .

# Create non-root user (good practice even in CI)
RUN useradd --create-home --shell /bin/bash --uid 1000 app \
    && mkdir -p /app/logs /app/staticfiles /app/media \
    && chown -R app:app /app /opt/venv

# Copy application code
COPY --chown=app:app . .

# Switch to non-root user
USER app

# No HEALTHCHECK in CI - tests will determine success/failure

# Default command - Run tests
CMD ["pytest", "-v", "--tb=short"]
