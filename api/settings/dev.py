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

# Local frontends: port 3000 (Next.js, Rsbuild) and 5173 (Vite), plus
# FRONTEND_URL. CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS in .env win.
_LOCAL_FRONTEND_ORIGINS = list(
    dict.fromkeys(
        [
            FRONTEND_URL,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
)
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=_LOCAL_FRONTEND_ORIGINS)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=_LOCAL_FRONTEND_ORIGINS)

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
        # watches.
        "django.utils.autoreload": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    }
)

# Enable template debug mode for better error reporting
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore[index]
