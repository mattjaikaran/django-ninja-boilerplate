"""Django settings for api project - Common settings.

This module contains settings that are common across all environments.
Environment-specific settings should be defined in dev.py or prod.py.
"""

import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import environ
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# for environment variable using django-environ library
# this allows you to use the .env file to set the environment variables
# throughout the entire application
env = environ.Env(
    # Set casting and default values
    DEBUG=(bool, False),
    ENVIRONMENT=(str, "development"),
    SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(list, []),
    # Database
    DB_NAME=(str, ""),
    DB_USER=(str, ""),
    DB_PASSWORD=(str, ""),
    DB_HOST=(str, ""),
    DB_PORT=(str, ""),
    DB_URL=(str, ""),
    # Valkey/Redis
    REDIS_URL=(str, "valkey://valkey:6379/0"),
    VALKEY_URL=(str, ""),
    CACHE_BACKEND=(str, "vcache"),
    # Task Queue
    TASK_BACKEND=(str, "celery"),
    HUEY_IMMEDIATE=(bool, False),
    CELERY_BROKER_URL=(str, "valkey://valkey:6379/0"),
    CELERY_RESULT_BACKEND=(str, "valkey://valkey:6379/0"),
    # Superuser defaults
    SUPERUSER_EMAIL=(str, "admin@example.com"),
    SUPERUSER_USERNAME=(str, "admin"),
    SUPERUSER_PASSWORD=(str, ""),
    SUPERUSER_FIRST_NAME=(str, "Admin"),
    SUPERUSER_LAST_NAME=(str, "User"),
    # Stripe (optional)
    STRIPE_PUBLISHABLE_KEY=(str, ""),
    STRIPE_SECRET_KEY=(str, ""),
    STRIPE_WEBHOOK_SECRET=(str, ""),
    # AWS S3 (optional)
    AWS_ACCESS_KEY_ID=(str, ""),
    AWS_SECRET_ACCESS_KEY=(str, ""),
    AWS_STORAGE_BUCKET_NAME=(str, ""),
    AWS_S3_REGION_NAME=(str, "us-east-1"),
)

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Environment setting
ENVIRONMENT = env("ENVIRONMENT", default="development")

# Default DEBUG — overridden in dev.py (True) and prod.py (False)
DEBUG = env("DEBUG", default=False)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# Application definition
INSTALLED_APPS = [
    #####
    # Django Unfold admin panel
    #####
    "unfold",  # django-unfold
    "unfold.contrib.filters",  # django-unfold-filters
    "unfold.contrib.forms",  # django-unfold-forms
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    #####
    # Django core packages
    #####
    "django.contrib.admin",  # admin
    "django.contrib.auth",  # auth
    "django.contrib.contenttypes",  # content types
    "django.contrib.sessions",  # sessions
    "django.contrib.messages",  # messages
    "django.contrib.staticfiles",  # static files
    #####
    # django-ninja-extra libraries
    #####
    "ninja_extra",  # django-ninja-extra
    "ninja_jwt",  # django-ninja-jwt
    "ninja_jwt.token_blacklist",  # JWT refresh-token blacklist (revocation + rotation)
    #####
    # user created apps
    #####
    "core",  # core app
    "todos",  # todos app
    "atlas",  # codebase atlas (interactive architecture map in admin)
    # Optional apps. Set FILES_ENABLED / WEBHOOKS_ENABLED (below) for files and
    # webhooks; uncomment the others to enable them:
    # "organizations",  # multi-tenancy / org membership
    # "notifications",  # in-app + email notifications
    # "billing",  # Stripe billing
    # third party packages
    #####
    "corsheaders",  # django-cors-headers for cross-origin requests
    "import_export",  # django-import-export for importing and exporting data
    "csp",  # django-csp for Content-Security-Policy headers
]

# Optional apps behind flags. Both default off. See docs/ARCHITECTURE.md.
# files: S3 presigned upload. Uploads are size-capped and magic-byte checked.
FILES_ENABLED = env.bool("FILES_ENABLED", default=False)
if FILES_ENABLED:
    INSTALLED_APPS += ["files"]
# Largest accepted upload, in bytes (presigned POST limit and local upload cap).
FILES_MAX_UPLOAD_BYTES = env.int("FILES_MAX_UPLOAD_BYTES", default=10 * 1024 * 1024)
# Accepted types. Only types with a known magic-byte signature are accepted:
# image/jpeg, image/png, image/gif, image/webp, application/pdf.
FILES_ALLOWED_CONTENT_TYPES = env.list(
    "FILES_ALLOWED_CONTENT_TYPES",
    default=["image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"],
)
# webhooks: outbound webhooks. Delivery is SSRF-guarded (webhooks/ssrf.py).
WEBHOOKS_ENABLED = env.bool("WEBHOOKS_ENABLED", default=False)
if WEBHOOKS_ENABLED:
    INSTALLED_APPS += ["webhooks"]
# Allow http:// webhook URLs outside DEBUG. Keep off: plain HTTP leaks payloads.
WEBHOOKS_ALLOW_HTTP = env.bool("WEBHOOKS_ALLOW_HTTP", default=False)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",  # security middleware
    # Serves collected static files when no nginx sits in front (single, PaaS).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "csp.middleware.CSPMiddleware",  # Content-Security-Policy headers
    "django.middleware.gzip.GZipMiddleware",  # Performance: Response compression
    "django.contrib.sessions.middleware.SessionMiddleware",  # session middleware
    "corsheaders.middleware.CorsMiddleware",  # django-cors-headers
    "django.middleware.common.CommonMiddleware",  # common middleware
    # Django CSRF, extended to the cookie-authenticated API (docs/COOKIE_AUTH.md)
    "core.security.cookie_auth.ApiCsrfMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",  # authentication middleware
    "django.contrib.messages.middleware.MessageMiddleware",  # message middleware
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Observability middleware (tracing, metrics, structured logging)
    "core.observability.middleware.ObservabilityMiddleware",
    # Audit logging middleware
    "core.audit.decorators.AuditContextMiddleware",  # Sets audit context for signals
    "core.audit.middleware.AuditLoggingMiddleware",  # Logs API requests/responses
]

# Performance: Compress responses larger than 1KB
GZIP_MIN_LENGTH = 1024

# Deployment defaults are secure; only explicit local settings disable Secure.
AUTH_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

ROOT_URLCONF = "api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",  # django templates
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,  # app directories
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",  # debug context processor
                "django.template.context_processors.request",  # request context processor
                "django.contrib.auth.context_processors.auth",  # auth context processor
                "django.contrib.messages.context_processors.messages",  # messages context processor
            ],
        },
    },
]

WSGI_APPLICATION = "api.wsgi.application"  # wsgi application

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# https://docs.djangoproject.com/en/5.2/ref/databases/#connection-pool
# Web processes use psycopg 3's connection pool. The pool replaces persistent
# connections, so CONN_MAX_AGE must stay 0 (Django raises ImproperlyConfigured
# otherwise). With a pool, CONN_HEALTH_CHECKS makes the pool check each
# connection before it hands it out.
# Each process owns its own pool: peak connections are
# processes x DB_POOL_MAX_SIZE, which must stay below Postgres max_connections.
# Task workers fork after Django loads, which breaks an inherited pool, so their
# Compose services set DB_POOL_ENABLED=false. See "Database connection pool" in
# docs/ARCHITECTURE.md.
DB_POOL_ENABLED = env.bool("DB_POOL_ENABLED", default=True)
DB_POOL_MIN_SIZE = env.int("DB_POOL_MIN_SIZE", default=2)
DB_POOL_MAX_SIZE = env.int("DB_POOL_MAX_SIZE", default=10)
# Seconds a request waits for a free pooled connection before it fails.
DB_POOL_TIMEOUT = env.float("DB_POOL_TIMEOUT", default=10.0)
if DB_POOL_MAX_SIZE < DB_POOL_MIN_SIZE:
    raise ImproperlyConfigured(
        f"DB_POOL_MAX_SIZE ({DB_POOL_MAX_SIZE}) must be >= "
        f"DB_POOL_MIN_SIZE ({DB_POOL_MIN_SIZE})."
    )

_db_options: dict[str, object] = {
    "connect_timeout": 10,
    # Query timeout (30 seconds)
    "options": "-c statement_timeout=30000",
}
if DB_POOL_ENABLED:
    _db_options["pool"] = {
        "min_size": DB_POOL_MIN_SIZE,
        "max_size": DB_POOL_MAX_SIZE,
        "timeout": DB_POOL_TIMEOUT,
    }

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": _db_options,
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Custom user model
AUTH_USER_MODEL = "core.User"

# Django Ninja JWT settings
# The JWT signing key is deliberately separate from SECRET_KEY so rotating the
# Django secret never invalidates outstanding access/refresh tokens, and so
# production can require a distinct value. Production (api.settings.prod) must
# reject an unset or SECRET_KEY-equal value; development and tests fall back to
# SECRET_KEY for zero-config setup.
NINJA_JWT_SIGNING_KEY = env("NINJA_JWT_SIGNING_KEY", default=SECRET_KEY)

# Access tokens are short-lived (60 minutes) and intentionally left valid until
# expiry after logout: revoking only the refresh token stops the refresh flow
# without a per-request blacklist lookup on every access-token use.
# Refresh tokens always rotate. core.security.refresh_tokens adds reuse
# detection (a rotated token presented again revokes all of the user's refresh
# tokens) and revokes them on every password change (core.models.User.save).
NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "TOKEN_OBTAIN_PAIR_REFRESH_INPUT_SCHEMA": (
        "core.security.refresh_tokens.TokenRefreshInputSchema"
    ),
    # Per-account and per-IP lockout shared with /api/auth/login.
    "TOKEN_OBTAIN_PAIR_INPUT_SCHEMA": (
        "core.security.brute_force.TokenObtainPairInputSchema"
    ),
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": NINJA_JWT_SIGNING_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("ninja_jwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "TOKEN_USER_CLASS": "core.User",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}

# Number of trusted reverse proxies in front of the app. Django Ninja reads
# ``NINJA_NUM_PROXIES`` and Ninja Extra reads ``NINJA_EXTRA["NUM_PROXIES"]``;
# keep both in sync so throttles derive the real client IP from
# X-Forwarded-For without trusting the first hop an attacker controls.
# Default 0 trusts no proxy (spoof-resistant); set 1 in the single-nginx
# deployment behind a trusted proxy.
TRUSTED_PROXY_COUNT = env.int("NINJA_NUM_PROXIES", default=0)

# Django Ninja Extra settings
NINJA_EXTRA = {
    "PAGINATION_CLASS": "ninja_extra.pagination.PageNumberPaginationExtra",  # included pagination
    "PAGINATION_PER_PAGE": 50,  # 50 items per page
    "INJECTOR_MODULES": [],  # injector modules
    "THROTTLE_CLASSES": [
        "ninja_extra.throttling.AnonRateThrottle",  # anonymous user throttling
        "ninja_extra.throttling.UserRateThrottle",  # authenticated user throttling
    ],
    "THROTTLE_RATES": {
        "user": "1000/day",  # authenticated general API
        "anon": "100/day",  # anonymous general API
        "anon-auth": "20/min",  # credential endpoints (login, token, verify)
        "anon-email": "5/min",  # magic-link request (email sending)
        "tasks": "60/min",  # task admin endpoints
    },
    "NUM_PROXIES": TRUSTED_PROXY_COUNT,  # trusted reverse proxies
    "ORDERING_CLASS": "ninja_extra.ordering.Ordering",  # included ordering
    "SEARCHING_CLASS": "ninja_extra.searching.Search",  # included searching
}

# Base Django Ninja reads the same count from the top-level setting.
NINJA_NUM_PROXIES = TRUSTED_PROXY_COUNT

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE = "en-us"  # language code
TIME_ZONE = "UTC"  # time zone
USE_I18N = True  # use i18n
USE_TZ = True  # use tz

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL = "/static/"
# Absolute so `collectstatic` writes where the compose static volume is mounted
# (/app/staticfiles); the nginx image serves that same path.
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files configuration
if ENVIRONMENT == "production" and env("AWS_STORAGE_BUCKET_NAME", default=""):
    # S3 Storage for production.
    # DEFAULT_FILE_STORAGE was removed in Django 5.1; use the STORAGES mapping.
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_DEFAULT_ACL = "public-read"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
else:
    # Local storage for development
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django.db.backends": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "import_export": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core.schemas": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core.controllers": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "todos": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# =============================================================================
# Valkey/Redis & Caching Configuration
# =============================================================================
# CACHE_BACKEND options: "vcache" (default, Rust-based), "valkey", "redis"
# Valkey is wire-compatible with Redis — same protocol, same commands.
CACHE_BACKEND_TYPE = env("CACHE_BACKEND", default="vcache")
VALKEY_URL = env(
    "VALKEY_URL", default=env("REDIS_URL", default="valkey://valkey:6379/0")
)
# Keep REDIS_URL as alias for backward compatibility
REDIS_URL = env("REDIS_URL", default=VALKEY_URL)

if CACHE_BACKEND_TYPE == "vcache":
    CACHES = {
        "default": {
            "BACKEND": "django_vcache.backend.ValkeyCache",
            "LOCATION": VALKEY_URL,
            "KEY_PREFIX": "boilerplate",
        }
    }
elif CACHE_BACKEND_TYPE == "valkey":
    CACHES = {
        "default": {
            "BACKEND": "django_valkey.cache.ValkeyCache",
            "LOCATION": VALKEY_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_valkey.client.DefaultClient",
            },
            "KEY_PREFIX": "boilerplate",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": VALKEY_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "boilerplate",
        }
    }

# Session configuration (use cache backend for performance)
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# =============================================================================
# Celery Configuration
# =============================================================================
# kombu has no valkey transport, so the broker needs the redis:// scheme even
# when the cache URL uses valkey://. Deriving it keeps a bare settings import
# (no .env, or a deployment that skipped the template) from producing a broker
# that cannot connect.
_BROKER_URL_DEFAULT = VALKEY_URL.replace("valkey://", "redis://", 1)
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=_BROKER_URL_DEFAULT)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=_BROKER_URL_DEFAULT)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
# django-celery-beat supplies the database scheduler and the admin pages for
# periodic tasks. It must be installed here or its models do not exist and
# `celery beat` fails to start.
INSTALLED_APPS += ["django_celery_beat"]
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Flower (Celery monitoring UI) — set FLOWER_URL to expose the Flower
# dashboard link in the admin sidebar and dashboard quick links.
FLOWER_URL = env("FLOWER_URL", default="")
os.environ.setdefault("FLOWER_URL", FLOWER_URL)

# =============================================================================
# Pluggable Task Backend
# =============================================================================
# Options: celery (default), huey, django_q, django_rq, dramatiq, none.
# none runs no worker: .delay() raises TaskDispatchDisabled (api/tasks).
TASK_BACKEND = env("TASK_BACKEND", default="celery")
_TASK_REDIS_URL = REDIS_URL.replace("valkey://", "redis://", 1)

# Huey configuration (when TASK_BACKEND=huey)
if TASK_BACKEND == "huey":
    INSTALLED_APPS += ["huey.contrib.djhuey"]
    HUEY = {
        "huey_class": "huey.RedisHuey",
        "name": "boilerplate",
        "url": _TASK_REDIS_URL,
        "immediate": env("HUEY_IMMEDIATE", default=False),
        "consumer": {
            "workers": 4,
            "worker_type": "thread",
        },
    }

# django-q2 configuration (when TASK_BACKEND=django_q)
if TASK_BACKEND == "django_q":
    INSTALLED_APPS += ["django_q"]
    Q_CLUSTER = {
        "name": "boilerplate",
        "workers": 4,
        "recycle": 500,
        "timeout": 60,
        "compress": True,
        "save_limit": 250,
        "queue_limit": 500,
        "cpu_affinity": 1,
        "label": "Django Q2",
        "redis": _TASK_REDIS_URL,
    }

# django-rq configuration (when TASK_BACKEND=django_rq)
if TASK_BACKEND == "django_rq":
    INSTALLED_APPS += ["django_rq"]
    RQ_QUEUES = {
        "default": {
            "URL": _TASK_REDIS_URL,
            "DEFAULT_TIMEOUT": 360,
        },
        "high": {
            "URL": _TASK_REDIS_URL,
            "DEFAULT_TIMEOUT": 360,
        },
        "low": {
            "URL": _TASK_REDIS_URL,
            "DEFAULT_TIMEOUT": 360,
        },
    }

# =============================================================================
# Centrifugo Real-Time Messaging
# =============================================================================
CENTRIFUGO_URL = env("CENTRIFUGO_URL", default="http://centrifugo:8000")
CENTRIFUGO_API_KEY = env("CENTRIFUGO_API_KEY", default="centrifugo-api-key")
CENTRIFUGO_TOKEN_SECRET = env(
    "CENTRIFUGO_TOKEN_SECRET", default="centrifugo-token-secret"
)
CENTRIFUGO_TOKEN_TTL = env.int("CENTRIFUGO_TOKEN_TTL", default=3600)  # 1 hour

# =============================================================================
# Payment Integration (Stripe)
# =============================================================================
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# =============================================================================
# Security Settings
# =============================================================================
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# =============================================================================
# Cookie auth, CSRF and CORS (contract: docs/COOKIE_AUTH.md)
# =============================================================================
# The frontend is a separate origin or container. It authenticates with
# httpOnly JWT cookies and sends X-CSRFToken on every unsafe request.
# USE_TLS=true only when a TLS-terminating proxy sits in front: it turns on
# Secure cookies here and the HTTPS redirect and HSTS in prod.py.
USE_TLS = env.bool("USE_TLS", default=False)

AUTH_COOKIE_ACCESS_NAME = "access_token"
AUTH_COOKIE_REFRESH_NAME = "refresh_token"
AUTH_COOKIE_ACCESS_PATH = "/api/"
# Only refresh and logout read the refresh token.
AUTH_COOKIE_REFRESH_PATH = "/api/auth/"
AUTH_COOKIE_SAMESITE = "Lax"
AUTH_COOKIE_SECURE = USE_TLS

# The client reads the csrftoken cookie and echoes it in X-CSRFToken.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = USE_TLS
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[FRONTEND_URL])
# ninja-jwt bearer endpoints return tokens in the body and set no cookie, so a
# forged cross-site request gains nothing. Signed webhook receivers verify the
# sender's signature instead of a CSRF token (Stripe: billing/webhooks.py).
API_CSRF_EXEMPT_PATHS = ["/api/token/", "/api/billing/webhooks/"]
# security.W003 looks for the exact CsrfViewMiddleware path; ApiCsrfMiddleware
# subclasses it and keeps Django's CSRF behaviour for every non-API view.
SILENCED_SYSTEM_CHECKS = ["security.W003"]

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[FRONTEND_URL])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# =============================================================================
# Content-Security-Policy (django-csp 4.0+)
# Covers the only HTML the API-only backend serves: the admin and the API
# docs. The frontend is a separate origin and sets its own CSP. Development
# reports violations only; prod.py enforces a stricter copy.
# =============================================================================
# Public so prod.py can build the enforced policy from the same directives.
CSP_DIRECTIVES = {
    "default-src": ("'self'",),
    "script-src": ("'self'", "'unsafe-inline'", "'unsafe-eval'"),
    "style-src": ("'self'", "'unsafe-inline'"),
    "img-src": ("'self'", "data:", "https:"),
    "font-src": ("'self'", "data:"),
    "connect-src": ("'self'",),
    "frame-ancestors": ("'none'",),
    "base-uri": ("'self'",),
    "form-action": ("'self'",),
}

# Both names are always defined so api.settings.prod can replace their contents
# without redefining a star-imported name. django-csp emits the enforced policy
# and the report-only policy as separate headers.
CONTENT_SECURITY_POLICY: dict[str, Any] = {}
CONTENT_SECURITY_POLICY_REPORT_ONLY: dict[str, Any] = {}
if ENVIRONMENT == "development":
    CONTENT_SECURITY_POLICY_REPORT_ONLY["DIRECTIVES"] = CSP_DIRECTIVES
else:
    CONTENT_SECURITY_POLICY["DIRECTIVES"] = CSP_DIRECTIVES

# =============================================================================
# Email Configuration
# =============================================================================
# Three backend options (set EMAIL_BACKEND in your .env):
#   1. Console (default/dev):
#      django.core.mail.backends.console.EmailBackend
#   2. Native Resend SDK backend (this package):
#      core.services.email.backends.ResendEmailBackend
#   3. Resend via django-anymail (alternative):
#      anymail.backends.resend.EmailBackend
#
# Docs: https://resend.com/docs/send-with-python
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
RESEND_API_KEY = env("RESEND_API_KEY", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# Anymail integration (used when EMAIL_BACKEND = anymail.backends.resend.EmailBackend)
if RESEND_API_KEY:
    ANYMAIL = {
        "RESEND_API_KEY": RESEND_API_KEY,
    }

# Legacy SMTP settings (used if EMAIL_BACKEND is overridden to SMTP)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# =============================================================================
# Admin Configuration
# =============================================================================
ADMIN_SITE_HEADER = env("ADMIN_SITE_HEADER", default="Django Ninja Boilerplate Admin")
ADMIN_SITE_TITLE = env("ADMIN_SITE_TITLE", default="Django Ninja Boilerplate Panel")
ADMIN_INDEX_TITLE = env(
    "ADMIN_INDEX_TITLE",
    default="Welcome to Django Ninja Boilerplate Panel",
)
ADMIN_SITE_URL = "/api/docs"
ADMIN_VIEW_SITE_NAME = "View Docs"
# Admin mount path, relative and with a trailing slash. Change it per deploy
# to keep the admin login off scanners' default path; failed admin logins also
# share the API login lockout (core.security.brute_force).
ADMIN_URL = env("ADMIN_URL", default="admin/").strip("/") + "/"
if ADMIN_URL == "/":
    raise ImproperlyConfigured("ADMIN_URL must not be empty.")

# Swagger UI (/api/docs) and /api/openapi.json: "public", "staff" (admin
# login required) or "off". Production (prod.py) defaults to "off".
API_DOCS = env("API_DOCS", default="public")
if API_DOCS not in {"public", "staff", "off"}:
    raise ImproperlyConfigured("API_DOCS must be one of: public, staff, off.")

# =============================================================================
# Codebase Atlas Configuration
# =============================================================================
# Interactive isometric architecture map rendered in the admin panel at
# /admin/atlas/. Set ATLAS_ENABLED=False to disable the page and its URLs.
# The data file caches a scan of the codebase; use the admin Regenerate
# button or `python manage.py atlas` to refresh it.
ATLAS_ENABLED = env.bool("ATLAS_ENABLED", default=True)
ATLAS_DATA_PATH = env("ATLAS_DATA_PATH", default=str(BASE_DIR / "atlas-data.json"))
ATLAS_CACHE_TTL = env.int("ATLAS_CACHE_TTL", default=3600)
# Mine the audit log for masked real request bodies as data packets
ATLAS_REAL_SAMPLES = env.bool("ATLAS_REAL_SAMPLES", default=True)
# Optional per-app prose metadata; apps can also ship an atlas.py module
ATLAS_METADATA: dict = {}

# =============================================================================
# Audit Logging Configuration
# =============================================================================
# Enable/disable audit logging
AUDIT_LOG_ENABLED = env.bool("AUDIT_LOG_ENABLED", default=True)

# API paths to audit (prefix matching)
AUDIT_LOG_PATHS = ["/api/"]

# Paths to exclude from audit logging
AUDIT_LOG_EXCLUDE_PATHS = [
    "/api/health/",
    "/api/docs",
    "/api/openapi.json",
    "/api/metrics",
]

# Whether to log request/response bodies (disable for privacy in production)
AUDIT_LOG_BODY = env.bool("AUDIT_LOG_BODY", default=False)

# Maximum body length to log (bytes)
AUDIT_LOG_MAX_BODY_LENGTH = 1000

# Models to exclude from automatic audit tracking
AUDIT_EXCLUDED_MODELS = [
    "AuditLog",
    "Session",
    "ContentType",
    "Permission",
    "LogEntry",
    "MigrationHistory",
    "Migration",
]

# Specific models to track (None = track all except excluded)
# AUDIT_TRACKED_MODELS = ["User", "Todo", "MyModel"]
AUDIT_TRACKED_MODELS = None

# =============================================================================
# API Key Authentication
# =============================================================================
API_KEY_AUTH_ENABLED = env.bool("API_KEY_AUTH_ENABLED", default=True)
API_KEY_HEADER = env("API_KEY_HEADER", default="X-API-Key")
API_KEY_PREFIX = env("API_KEY_PREFIX", default="bnp")

# =============================================================================
# Observability Configuration
# =============================================================================
# Application version (used in metrics and health checks)
VERSION = env("APP_VERSION", default="1.12.0")

# OpenTelemetry Configuration. OTEL_ENABLED starts tracing in CoreConfig.ready()
# and needs the `observability` extra, which the Docker images install.
OTEL_ENABLED = env.bool("OTEL_ENABLED", default=False)
OTEL_SERVICE_NAME = env("OTEL_SERVICE_NAME", default="django-ninja-app")
OTEL_EXPORTER_OTLP_ENDPOINT = env(
    "OTEL_EXPORTER_OTLP_ENDPOINT", default="http://localhost:4317"
)
OTEL_CONSOLE_EXPORT = env.bool("OTEL_CONSOLE_EXPORT", default=False)

# Sentry or GlitchTip (same DSN format). A DSN starts the SDK in
# CoreConfig.ready() and needs the `sentry` extra. PII is scrubbed: see
# core/observability/sentry.py.
SENTRY_DSN = env("SENTRY_DSN", default="")
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)

# =============================================================================
# AI and data layer (opt-in, `ai` extra). See docs/AI_LAYER.md.
# =============================================================================
# AI_ENABLED installs core.ai: the pgvector example models and the migration
# that creates the `vector` extension. Postgres needs pgvector
# (POSTGRES_IMAGE=pgvector/pgvector:pg17 in Compose).
AI_ENABLED = env.bool("AI_ENABLED", default=False)
if AI_ENABLED:
    INSTALLED_APPS += ["core.ai"]
# Any OpenAI-compatible API: OpenAI, Ollama, vLLM, OpenRouter, a LiteLLM proxy.
AI_BASE_URL = env("AI_BASE_URL", default="")
AI_API_KEY = env("AI_API_KEY", default="")
# Reported as gen_ai.provider.name on traces (openai, anthropic, ...).
AI_PROVIDER_NAME = env("AI_PROVIDER_NAME", default="openai")
AI_CHAT_MODEL = env("AI_CHAT_MODEL", default="")
AI_EMBEDDING_MODEL = env("AI_EMBEDDING_MODEL", default="")
AI_TIMEOUT = env.float("AI_TIMEOUT", default=60.0)
# Seconds a chat response stays in the cache. 0 turns the cache off.
AI_CACHE_TTL = env.int("AI_CACHE_TTL", default=3600)

# App-level MCP server at /api/mcp (core/mcp/server.py). Needs the `ai` extra
# and an ASGI server. Clients send a JWT access token as a Bearer token.
MCP_ENABLED = env.bool("MCP_ENABLED", default=False)
# Public origin of this API, used in the MCP auth metadata.
MCP_BASE_URL = env("MCP_BASE_URL", default="http://localhost:8000")
# operationIds of the GET routes exposed as MCP tools (docs/openapi/openapi.json).
MCP_TOOLS = env.list(
    "MCP_TOOLS",
    default=[
        "auth_get_current_user",
        "todo_list_todos",
        "todo_search_todos",
        "todo_get_todo",
    ],
)

# Enable structured JSON logging in production
USE_STRUCTURED_LOGGING = env.bool(
    "USE_STRUCTURED_LOGGING", default=ENVIRONMENT == "production"
)

# Slow request threshold for logging (in milliseconds)
SLOW_REQUEST_THRESHOLD_MS = env.int("SLOW_REQUEST_THRESHOLD_MS", default=1000)

# Update LOGGING for structured JSON format when enabled
if USE_STRUCTURED_LOGGING:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "trace_context": {
                "()": "core.observability.logging.TraceContextFilter",
            },
            "request_context": {
                "()": "core.observability.logging.RequestContextFilter",
            },
        },
        "formatters": {
            "json": {
                "()": "core.observability.logging.StructuredJsonFormatter",
                "include_trace_context": True,
                "extra_fields": {"app": OTEL_SERVICE_NAME},
            },
            "verbose": {
                "format": "[{asctime}] {levelname} {name} [{trace_id}] {message}",
                "style": "{",
            },
            "simple": {
                "format": "{levelname} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console_json": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": ["trace_context", "request_context"],
            },
            "console": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
                "filters": ["trace_context", "request_context"],
            },
        },
        "root": {
            "handlers": ["console_json"],
            "level": "INFO",
        },
        "loggers": {
            "django": {
                "handlers": ["console_json"],
                "level": "INFO",
                "propagate": False,
            },
            "django.request": {
                "handlers": ["console_json"],
                "level": "INFO",
                "propagate": False,
            },
            "django.db.backends": {
                "handlers": ["console_json"],
                "level": "WARNING",
                "propagate": False,
            },
            "django.server": {
                "handlers": ["console_json"],
                "level": "INFO",
                "propagate": False,
            },
            "core": {
                "handlers": ["console_json"],
                "level": "INFO",
                "propagate": False,
            },
            "core.observability": {
                "handlers": ["console_json"],
                "level": "INFO",
                "propagate": False,
            },
            "api": {
                "handlers": ["console_json"],
                "level": "INFO",
                "propagate": False,
            },
            "celery": {
                "handlers": ["console_json"],
                "level": "INFO",
                "propagate": False,
            },
            "todos": {
                "handlers": ["console_json"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }


# ── Django Unfold Admin Configuration ──────────────────────────────────
from .unfold import UNFOLD  # noqa: F401 (re-exported into settings)
