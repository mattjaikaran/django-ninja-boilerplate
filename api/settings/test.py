"""Django settings for api project - Test environment.

Uses SQLite by default for fast local testing.
In CI, PostgreSQL is used via environment variables.
"""

import os

from .common import *

# Test mode
DEBUG = False
TESTING = True

# Use a fixed secret key for tests
SECRET_KEY = "test-secret-key-not-for-production"

ALLOWED_HOSTS = ["*"]

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
