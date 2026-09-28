"""Django settings for api project - Development environment.

This module contains settings specific to the development environment.
"""

from .common import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG", default=True)

# Allowed hosts for development
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0", "django"]
)

# CORS settings for development
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://0.0.0.0:3000",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://0.0.0.0:3000",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# Django Debug Toolbar — uncomment INSTALLED_APPS and MIDDLEWARE entries
# in common.py to activate. These settings are ready when you do.
INTERNAL_IPS = [
    "127.0.0.1",
    "0.0.0.0",
]


def show_toolbar(request):
    return True


DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": show_toolbar,
}

# Development-specific logging
LOGGING["loggers"].update(  # type: ignore[attr-defined]
    {
        "django": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        # At DEBUG, runserver's StatReloader logs one line for every file it
        # watches, including each torch module that Laya imports.
        "django.utils.autoreload": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    }
)

# Enable template debug mode for better error reporting
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore[index]

# =============================================================================
# Development-only feature flags
# =============================================================================
# Decisions app (System One decision engine). ENABLE_DECISION_MCP stays under
# .env control: the `mcp` Compose service sets it, and the worker images do
# not install django-ai-boost, so forcing it on made every worker warn.
ENABLE_DECISIONS = True
