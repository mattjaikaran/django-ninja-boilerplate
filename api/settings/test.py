"""Django settings for api project - Test environment.

Uses SQLite by default for fast local testing.
In CI, PostgreSQL is used via environment variables.
"""

import os

from .common import *
from .common import INSTALLED_APPS as COMMON_INSTALLED_APPS

# Test mode
DEBUG = False
TESTING = True
AUTH_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

# Use a fixed secret key for tests
SECRET_KEY = "test-secret-key-not-for-production"

# Test tokens must not depend on blank or production keys from a local .env.
NINJA_JWT_SIGNING_KEY = "test-jwt-signing-key-not-for-production"
NINJA_JWT = {**NINJA_JWT, "SIGNING_KEY": NINJA_JWT_SIGNING_KEY}

ALLOWED_HOSTS = ["*"]

# The billing app is commented out of INSTALLED_APPS by default. Install its
# models so billing/tests runs in the default suite; its routes stay off the
# main API (and the exported OpenAPI). billing/tests/urls.py mounts them.
if "billing" not in COMMON_INSTALLED_APPS:
    INSTALLED_APPS = [*COMMON_INSTALLED_APPS, "billing"]

# Database: Use PostgreSQL in CI, SQLite locally
# CI sets the CI=1 env var; locally we fall back to SQLite for zero-setup testing
if os.environ.get("CI"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "test_db"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test_db.sqlite3",
        }
    }

# Use local memory cache for tests (no Redis required)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Use database sessions for tests (no cache dependency)
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Disable Celery in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use console email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
# Send account emails inline so tests can read mail.outbox.
ACCOUNT_EMAIL_SYNC = True

# Disable audit logging middleware in tests to reduce noise
MIDDLEWARE = [m for m in MIDDLEWARE if "Audit" not in m and "Observability" not in m]

# Faster password hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Simplified logging for tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "console": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}
