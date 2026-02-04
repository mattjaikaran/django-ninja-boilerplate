"""Django settings package.

This package contains environment-specific Django settings.

Import the appropriate settings module based on the DJANGO_ENVIRONMENT
environment variable:
- dev: Development settings
- prod: Production settings

Defaults to dev if DJANGO_ENVIRONMENT is not set.
"""

import os

# Default to dev environment
environment = os.environ.get("DJANGO_ENVIRONMENT", "dev")

if environment == "prod":
    from .prod import *
else:
    from .dev import *
