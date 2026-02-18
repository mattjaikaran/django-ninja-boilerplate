"""Django settings package.

Auto-detects the environment from env vars and loads the appropriate
settings module.

Supported env vars (checked in order):
- DJANGO_SETTINGS_MODULE: Full module path (e.g., "api.settings.prod")
- DJANGO_ENVIRONMENT / DJANGO_ENV: Shorthand name (e.g., "prod", "dev")

Shorthand mappings:
- "dev" / "development" / "local" -> api.settings.dev
- "prod" / "production" -> api.settings.prod

Defaults to dev with a warning if no environment is detected.
"""

import logging
import os
import warnings

logger = logging.getLogger(__name__)

# Environment shorthand mappings
_ENV_MAP = {
    "dev": "dev",
    "development": "dev",
    "local": "dev",
    "prod": "prod",
    "production": "prod",
}

# Check DJANGO_SETTINGS_MODULE first - if it's already set to a specific
# module (not just "api.settings"), respect that
settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
if settings_module and settings_module not in ("api.settings", ""):
    # DJANGO_SETTINGS_MODULE is explicitly set to a specific module
    # Django will handle loading it directly
    pass
else:
    # Auto-detect from DJANGO_ENVIRONMENT or DJANGO_ENV
    environment = os.environ.get(
        "DJANGO_ENVIRONMENT",
        os.environ.get("DJANGO_ENV", ""),
    ).lower()

    resolved = _ENV_MAP.get(environment)

    if not resolved:
        if environment:
            warnings.warn(
                f"Unknown DJANGO_ENVIRONMENT='{environment}', falling back to dev settings",
                stacklevel=1,
            )
        resolved = "dev"

    if resolved == "prod":
        from .prod import *  # noqa: F403, F401
    else:
        from .dev import *  # noqa: F403, F401
