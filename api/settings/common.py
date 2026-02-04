"""Django settings for api project - Common settings.

This module contains settings that are common across all environments.
Environment-specific settings should be defined in dev.py or prod.py.
"""

import os
from datetime import timedelta
from pathlib import Path

import environ

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
    # Redis
    REDIS_URL=(str, "redis://redis:6379/0"),
    # Celery
    CELERY_BROKER_URL=(str, "redis://redis:6379/0"),
    CELERY_RESULT_BACKEND=(str, "redis://redis:6379/0"),
    # Superuser defaults
    SUPERUSER_EMAIL=(str, "admin@example.com"),
    SUPERUSER_USERNAME=(str, "admin"),
    SUPERUSER_PASSWORD=(str, "Password123!"),
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
    #####
    # user created apps
    #####
    "core",  # core app
    "todos",  # todos app
    #####
    # third party packages
    #####
    "corsheaders",  # django-cors-headers for cross-origin requests
    "import_export",  # django-import-export for importing and exporting data
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",  # security middleware
    "django.middleware.gzip.GZipMiddleware",  # Performance: Response compression
    "django.contrib.sessions.middleware.SessionMiddleware",  # session middleware
    "corsheaders.middleware.CorsMiddleware",  # django-cors-headers
    "django.middleware.common.CommonMiddleware",  # common middleware
    "django.middleware.csrf.CsrfViewMiddleware",  # csrf view middleware
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

ROOT_URLCONF = "api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",  # django templates
        "DIRS": [],  # directories
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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
        # Performance: Connection pooling (keep connections alive for 10 minutes)
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            # Performance: Connection timeout
            "connect_timeout": 10,
            # Performance: Query timeout (30 seconds)
            "options": "-c statement_timeout=30000",
        },
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
NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
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
        "user": "1000/day",  # 1000 requests per day for authenticated users
        "anon": "100/day",  # 100 requests per day for anonymous users
    },
    "NUM_PROXIES": None,  # number of proxies
    "ORDERING_CLASS": "ninja_extra.ordering.Ordering",  # included ordering
    "SEARCHING_CLASS": "ninja_extra.searching.Search",  # included searching
}

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE = "en-us"  # language code
TIME_ZONE = "UTC"  # time zone
USE_I18N = True  # use i18n
USE_TZ = True  # use tz

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL = "static/"
STATIC_ROOT = "static/"

# Media files configuration
if ENVIRONMENT == "production" and env("AWS_STORAGE_BUCKET_NAME", default=""):
    # S3 Storage for production
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
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
# Redis & Caching Configuration
# =============================================================================
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
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
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# =============================================================================
# Payment Integration (Stripe)
# =============================================================================
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# =============================================================================
# Security Settings
# =============================================================================
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Production security settings (enabled when not in DEBUG mode)
# Note: These should be configured in prod.py for production environment
# SECURE_SSL_REDIRECT = True
# SECURE_HSTS_SECONDS = 31536000  # 1 year
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True

# =============================================================================
# Email Configuration
# =============================================================================
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

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
    "/api/metrics/",
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
# Observability Configuration
# =============================================================================
# Application version (used in metrics and health checks)
VERSION = env("APP_VERSION", default="1.0.0")

# OpenTelemetry Configuration
OTEL_SERVICE_NAME = env("OTEL_SERVICE_NAME", default="django-ninja-app")
OTEL_EXPORTER_OTLP_ENDPOINT = env(
    "OTEL_EXPORTER_OTLP_ENDPOINT", default="http://localhost:4317"
)
OTEL_CONSOLE_EXPORT = env.bool("OTEL_CONSOLE_EXPORT", default=False)

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
