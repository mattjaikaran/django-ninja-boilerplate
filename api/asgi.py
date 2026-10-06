"""ASGI config for api project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from collections.abc import Awaitable, Callable
from typing import Any

from django.conf import settings
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

application: Callable[..., Awaitable[Any]] = get_asgi_application()

if settings.MCP_ENABLED:
    # Read-only MCP server at /api/mcp (core/mcp/server.py, `ai` extra).
    from core.mcp.server import with_mcp

    application = with_mcp(application)
