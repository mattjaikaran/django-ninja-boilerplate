"""Django settings for api project - Production environment.

This module contains settings specific to the production environment.
"""

import logging

from django.core.exceptions import ImproperlyConfigured

from .common import *

# Values committed to this repository (templates, compose dev fallbacks, the
# old deploy/centrifugo/config.json). Treat them as public.
_INSECURE_REALTIME_SECRETS = {
    "centrifugo-token-secret",
    "dev-centrifugo-token-secret",
    "centrifugo-api-key",
    "dev-centrifugo-api-key",
    "admin",
    "admin-secret",
}
if CENTRIFUGO_TOKEN_SECRET in _INSECURE_REALTIME_SECRETS:
    raise ImproperlyConfigured(
        "Set CENTRIFUGO_TOKEN_SECRET to a unique value in production."
    )
if CENTRIFUGO_API_KEY in _INSECURE_REALTIME_SECRETS:
    raise ImproperlyConfigured(
        "Set CENTRIFUGO_API_KEY to a unique value in production."
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

# The API docs and OpenAPI schema map every route. Off unless the deploy
# opts in with API_DOCS=staff (admin login) or API_DOCS=public.
API_DOCS = env("API_DOCS", default="off")
if API_DOCS not in {"public", "staff", "off"}:
    raise ImproperlyConfigured("API_DOCS must be one of: public, staff, off.")

# CORS and CSRF origins and USE_TLS live in common.py. Set FRONTEND_URL, or
# CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS, per deploy.

# Cookie auth needs TLS. Browsers drop Secure cookies on plain HTTP for every
# host but localhost, and cookies without Secure leak the session, CSRF and
# JWT cookies in clear text. So production requires USE_TLS=true: a TLS proxy
# in front, forwarding X-Forwarded-Proto: https (the bundled nginx passes it
# through). ALLOW_INSECURE_COOKIES=true lets these settings run over plain
# HTTP for a local smoke run only; ENVIRONMENT=production rejects it.
ALLOW_INSECURE_COOKIES = env.bool("ALLOW_INSECURE_COOKIES", default=False)
if not USE_TLS and (ENVIRONMENT == "production" or not ALLOW_INSECURE_COOKIES):
    raise ImproperlyConfigured(
        "USE_TLS=false: cookie auth needs TLS outside localhost. Put a TLS proxy "
        "in front and set USE_TLS=true (docs/COOKIE_AUTH.md). For a local "
        "plain-HTTP smoke run only, set ALLOW_INSECURE_COOKIES=true with "
        "ENVIRONMENT other than production."
    )

# Security settings for production. Every setting that presumes the site is
# served over HTTPS is gated on USE_TLS so a plain-HTTP deployment (the bundled
# nginx convention) never emits headers or redirects that point at a scheme the
# deployment does not serve. HSTS is ignored by browsers over HTTP and
# SECURE_HSTS_PRELOAD is dangerous: a preloaded domain that does not serve TLS
# becomes unreachable.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if USE_TLS:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    # includeSubDomains and preload are hard to undo and break any plain-HTTP
    # subdomain, so each one is opt-in.
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
        "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False
    )
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Platform health checks call the container over plain HTTP without
    # X-Forwarded-Proto, so a redirect would mark the deployment unhealthy.
    # Exempt only the public, I/O-free and readiness routes of
    # api.healthcheck; staff-only detail routes still redirect. Patterns match
    # request.path without its leading slash.
    SECURE_REDIRECT_EXEMPT = [
        r"^api/health/$",
        r"^api/health/liveness$",
        r"^api/health/readiness$",
    ]
else:
    # Local plain-HTTP smoke run (ALLOW_INSECURE_COOKIES): no HSTS or redirect.
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

# Secure cookies whenever TLS is on, which production requires (see above).
SESSION_COOKIE_SECURE = USE_TLS
CSRF_COOKIE_SECURE = USE_TLS
AUTH_COOKIE_SECURE = USE_TLS
if not USE_TLS:
    logging.getLogger("api.settings").error(
        "ALLOW_INSECURE_COOKIES=true: production settings over plain HTTP, "
        "cookies without Secure. Never use this on a reachable host."
    )
