"""Sentry or GlitchTip error reporting with PII scrubbed before send.

Started by ``CoreConfig.ready()`` when ``SENTRY_DSN`` is set. Needs the
`sentry` extra; without it, development logs an error and continues, and
every other ``ENVIRONMENT`` refuses to start. GlitchTip accepts the same SDK
and DSN format.

What leaves the process:
- ``send_default_pii=False``: no user email, username, IP, cookies or request
  bodies from the integrations.
- ``include_local_variables=False``: no stack-frame locals, which can hold
  tokens, passwords or user data.
- The event scrubber removes the keys in ``SCRUBBED_KEYS`` (exact match,
  case-insensitive) at any depth, on top of the SDK defaults.
"""

from __future__ import annotations

import logging

from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# Names this project uses for secrets that the SDK's exact-match default
# denylist does not cover (auth cookies, headers, settings).
SCRUBBED_KEYS = [
    "access",
    "access_token",
    "refresh",
    "refresh_token",
    "csrftoken",
    "x-csrftoken",
    "x_csrftoken",
    "x-api-key",
    "x_api_key",
    "http_x_api_key",
    "http_authorization",
    "api_token",
    "client_secret",
    "secret_key",
    "signing_key",
    "otp",
    "code",
    "email",
]


def init_sentry(
    *, dsn: str, environment: str, release: str, traces_sample_rate: float
) -> bool:
    """Start the Sentry SDK with the Django integration and PII scrubbing.

    When sentry-sdk is not installed, development (``environment ==
    "development"``) logs an error and returns False. Every other environment
    raises ``ImproperlyConfigured``, so a deploy with a DSN never runs without
    error reporting.
    """
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber
    except ImportError as exc:
        message = (
            "SENTRY_DSN is set but sentry-sdk is not installed. Install the "
            "`sentry` extra (`uv sync --extra sentry`, or build the image with "
            'UV_EXTRAS="sentry"), or unset SENTRY_DSN.'
        )
        if environment != "development":
            raise ImproperlyConfigured(message) from exc
        logger.error("%s Errors are NOT reported.", message)
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        include_local_variables=False,
        event_scrubber=EventScrubber(
            denylist=[*DEFAULT_DENYLIST, *SCRUBBED_KEYS], recursive=True
        ),
    )
    return True
