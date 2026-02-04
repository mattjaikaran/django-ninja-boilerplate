# Django Ninja Boilerplate - Unified Multi-Stage Dockerfile
# ============================================================
# This Dockerfile uses multi-stage builds with named targets that can be
# selected via the --target flag. This eliminates the need for multiple
# Dockerfile variants (e.g., Dockerfile.uv).
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


# ===========================================
# Stage 1: BASE - Common system dependencies
# ===========================================
# This stage sets up the foundational system packages and environment
# variables that are shared across all other stages.
FROM python:3.14-slim AS base

# Metadata labels for container identification
LABEL maintainer="Matt Jaikaran <info@mattjaikaran.com>" \
      version="1.0.0" \
      description="Django Ninja API Boilerplate" \
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

# Install common runtime dependencies needed by all stages
# - libpq5: PostgreSQL client library for psycopg2
# - curl: HTTP client for health checks
# - netcat-openbsd: Network utility for service readiness checks
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
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
# - build-essential: C compiler and related tools
# - libpq-dev: PostgreSQL headers for psycopg2 compilation
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy only dependency files first for better layer caching
# Changes to application code won't invalidate dependency cache
COPY pyproject.toml uv.lock* README.md ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv

# Install production dependencies only (no dev dependencies)
RUN uv pip install --no-cache -e .


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

# Copy uv from builder for installing dev dependencies
COPY --from=builder /root/.local/bin/uv /usr/local/bin/uv

# Copy dependency files and install dev dependencies
COPY pyproject.toml uv.lock* README.md ./
RUN uv pip install --no-cache -e ".[dev]" 2>/dev/null || uv pip install --no-cache -e .

# Create non-root user for security (even in development)
RUN useradd --create-home --shell /bin/bash --uid 1000 app \
    && mkdir -p /app/logs /app/staticfiles /app/media \
    && chown -R app:app /app /opt/venv

# Copy application code (will be overridden by volume mount in docker-compose)
COPY --chown=app:app . .

# Copy and set permissions for entrypoint scripts
COPY --chown=app:app docker-entrypoint.sh docker-entrypoint-dev.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/docker-entrypoint-dev.sh

# Switch to non-root user
USER app

# Expose port
EXPOSE 8000

# Health check for development
# More lenient timing for development environment
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Default command - Django development server with hot reload
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


# ===========================================
# Stage 4: PRODUCTION - Optimized runtime
# ===========================================
# This stage creates the smallest possible production image with:
# - Only runtime dependencies
# - Non-root user for security
# - Optimized Gunicorn configuration
# - Pre-compiled static files
FROM base AS production

# Production-specific environment
# PYTHONOPTIMIZE=2: Remove docstrings and assert statements
ENV PYTHONOPTIMIZE=2

# Copy virtual environment from builder (no dev dependencies)
COPY --from=builder /opt/venv /opt/venv

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 app \
    && mkdir -p /app/logs /app/staticfiles /app/media \
    && chown -R app:app /app

# Copy application code
COPY --chown=app:app . .

# Copy and set permissions for entrypoint scripts
COPY --chown=app:app docker-entrypoint.sh docker-entrypoint-dev.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/docker-entrypoint-dev.sh

# Switch to non-root user
USER app

# Collect static files at build time
RUN python manage.py collectstatic --noinput --settings=api.settings 2>/dev/null || true

# Expose port
EXPOSE 8000

# Production health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Default command - Production Gunicorn with optimized settings
# Workers = (2 * CPU cores) + 1, adjust based on your needs
# --worker-tmp-dir /dev/shm: Uses RAM for worker heartbeat files (faster)
# --max-requests: Recycle workers after N requests to prevent memory leaks
CMD ["gunicorn", "api.wsgi:application", \
    "--bind", "0.0.0.0:8000", \
    "--workers", "3", \
    "--threads", "2", \
    "--worker-class", "gthread", \
    "--worker-tmp-dir", "/dev/shm", \
    "--timeout", "120", \
    "--keep-alive", "5", \
    "--max-requests", "1000", \
    "--max-requests-jitter", "50", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--capture-output", \
    "--enable-stdio-inheritance"]


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

# Copy uv from builder for installing test dependencies
COPY --from=builder /root/.local/bin/uv /usr/local/bin/uv

# Copy dependency files and install test/dev dependencies
COPY pyproject.toml uv.lock* README.md ./
RUN uv pip install --no-cache -e ".[dev]" 2>/dev/null || uv pip install --no-cache -e .

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
