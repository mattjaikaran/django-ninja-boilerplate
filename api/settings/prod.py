"""Django settings for api project - Production environment.

This module contains settings specific to the production environment.
"""

from django.core.exceptions import ImproperlyConfigured

from .common import *

_INSECURE_REALTIME_SECRETS = {
    "centrifugo-token-secret",
    "dev-centrifugo-token-secret",
}
if CENTRIFUGO_TOKEN_SECRET in _INSECURE_REALTIME_SECRETS:
    raise ImproperlyConfigured(
        "Set CENTRIFUGO_TOKEN_SECRET to a unique value in production."
    )

# A production deploy must supply its own secrets explicitly. common.py reads
# SECRET_KEY with an empty-string default, so an unset key silently forges
# every signature; reject it before anything else runs.
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Set SECRET_KEY to a unique, non-empty value in production."
    )

# JWT refresh rotation signs tokens with a key separate from SECRET_KEY
# (common.py defines NINJA_JWT_SIGNING_KEY with a SECRET_KEY fallback for
# dev/test). Production must set it explicitly and distinct from SECRET_KEY,
# otherwise rotating the Django secret would also invalidate every issued token.
_jwt_signing_key = env("NINJA_JWT_SIGNING_KEY", default=None)
if not _jwt_signing_key or _jwt_signing_key == SECRET_KEY:
    raise ImproperlyConfigured(
        "Set NINJA_JWT_SIGNING_KEY to a unique value distinct from SECRET_KEY "
        "in production."
    )


# SECURITY WARNING: don't run with debug turned on in production!
# Forced off regardless of the DEBUG env var: a development .env (DEBUG=1) must
# never leak into a production settings load.
DEBUG = False

# Production allowed hosts
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# CORS settings for production
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

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

# SSL settings.
# Defaults to False because the bundled nginx serves plain HTTP on port 80 and
# forwards X-Forwarded-Proto: http. Set USE_TLS=true only when a TLS-terminating
# proxy sits in front; otherwise SECURE_SSL_REDIRECT redirects every request to
# an https:// port that nothing listens on.
USE_TLS = env.bool("USE_TLS", default=False)

# Security settings for production. Every setting that presumes the site is
# served over HTTPS is gated on USE_TLS so a plain-HTTP deployment (the bundled
# nginx convention) never emits headers or redirects that point at a scheme the
# deployment does not serve. HSTS is ignored by browsers over HTTP and
# SECURE_HSTS_PRELOAD is dangerous: a preloaded domain that does not serve TLS
# becomes unreachable.
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if USE_TLS:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    # Plain-HTTP deployment: keep HSTS, SSL redirect, and secure cookies off so
    # requests reach the port-80 listener unchanged.
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Email backend for production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# File storage for production (can be configured for S3, etc.)
# Uncomment and configure if using AWS S3
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
# STATICFILES_STORAGE = 'storages.backends.s3boto3.S3StaticStorage'

# AWS S3 settings (if used)
# AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
# AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
# AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
# AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
# AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="")
# AWS_DEFAULT_ACL = None
# AWS_S3_OBJECT_PARAMETERS = {
#     'CacheControl': 'max-age=86400',
# }

# Production logging - only use file logging in Docker
import os

if os.path.exists("/app/logs"):
    LOGGING["handlers"].update(  # type: ignore[attr-defined]
        {
            "file": {
                "level": "INFO",
                "class": "logging.FileHandler",
                "filename": "/app/logs/django.log",
                "formatter": "verbose",
            },
        }
    )

    LOGGING["loggers"].update(  # type: ignore[attr-defined]
        {
            "django": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "django.request": {
                "handlers": ["console", "file"],
                "level": "ERROR",
                "propagate": False,
            },
            "django.security": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
        }
    )
else:
    # Non-Docker production environment - only console logging
    LOGGING["loggers"].update(  # type: ignore[attr-defined]
        {
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "django.request": {
                "handlers": ["console"],
                "level": "ERROR",
                "propagate": False,
            },
            "django.security": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False,
            },
        }
    )

# Database connection pooling for production
DATABASES["default"].update(
    {
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
)

# =============================================================================
# Content-Security-Policy — production: enforce, no unsafe-inline/eval.
# django-csp 4.x reads CONTENT_SECURITY_POLICY (enforced) and
# CONTENT_SECURITY_POLICY_REPORT_ONLY separately. Build the enforced policy
# here from the shared directives instead of mutating common.py's object, so
# this module imports whatever ENVIRONMENT is set.
# =============================================================================
_CSP_DIRECTIVES: dict[str, tuple[str, ...] | bool] = {
    **CSP_DIRECTIVES,
    "script-src": ("'self'",),
    "style-src": ("'self'",),
}
if USE_TLS:
    # Only over HTTPS: over plain HTTP this would upgrade every subresource to
    # a scheme the deployment does not serve.
    _CSP_DIRECTIVES["upgrade-insecure-requests"] = True
CONTENT_SECURITY_POLICY["DIRECTIVES"] = _CSP_DIRECTIVES
CONTENT_SECURITY_POLICY_REPORT_ONLY.clear()

# Session security for production
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
if USE_TLS:
    SESSION_COOKIE_SECURE = True

# CSRF security for production
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
if USE_TLS:
    CSRF_COOKIE_SECURE = True
