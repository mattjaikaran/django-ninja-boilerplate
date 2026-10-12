"""Django settings for api project - Test environment.

Uses SQLite by default for fast local testing.
Set TEST_DB=postgres to use PostgreSQL via the DB_* environment variables.
CI is ignored on purpose: agent shells and runners set it for unrelated reasons.
common.py skips the local .env for these settings unless DJANGO_READ_DOT_ENV=1,
so every pytest run (gauntlet, agents, IDEs) gives the same result on every
machine. `just test-integration` sets DJANGO_READ_DOT_ENV=1 for the DB
credentials that Compose also takes from .env.
"""

import os

from .common import *
from .common import INSTALLED_APPS as COMMON_INSTALLED_APPS

# Test mode
DEBUG = False
TESTING = True

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

# Database: SQLite by default, PostgreSQL only when TEST_DB=postgres.
# Do not key this off CI; many shells set CI=true for unrelated reasons.
if os.environ.get("TEST_DB", "").lower() == "postgres":
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
