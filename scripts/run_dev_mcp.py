#!/usr/bin/env python3
"""Start the development MCP server (django-ai-boost over SSE) with guards.

django-ai-boost gives a coding agent read access to the Django project: setting
values, model rows, the URL map, migrations, system checks, and recent logs.
This launcher refuses to start unless all of these are true:

- ``DJANGO_SETTINGS_MODULE`` is ``api.settings.dev``.
- ``settings.DEBUG`` is true.
- ``DJANGO_MCP_AUTH_TOKEN`` holds at least 32 characters.

The server then requires ``Authorization: Bearer <token>`` on ``/sse`` and
``/messages/``, and rejects a ``Host`` header other than ``localhost`` or
``127.0.0.1``. The host check stops DNS rebinding from a browser on your
machine and calls from other containers by service name.

Usage:
    python scripts/run_dev_mcp.py [--host 0.0.0.0] [--port 8001]

Exit: 2 = a guard refused to start
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

REQUIRED_SETTINGS = "api.settings.dev"
TOKEN_ENV = "DJANGO_MCP_AUTH_TOKEN"
MIN_TOKEN_LENGTH = 32
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


def refuse(reason: str) -> None:
    """Print why the server will not start and exit with status 2."""
    print(f"run_dev_mcp: refusing to start: {reason}", file=sys.stderr)
    raise SystemExit(2)


def check_environment() -> str:
    """Apply the startup guards and return the bearer token."""
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    if settings_module != REQUIRED_SETTINGS:
        refuse(
            f"DJANGO_SETTINGS_MODULE is {settings_module!r}; "
            f"this server runs only with {REQUIRED_SETTINGS!r}."
        )

    token = os.environ.get(TOKEN_ENV, "")
    if len(token) < MIN_TOKEN_LENGTH:
        refuse(
            f"{TOKEN_ENV} must hold at least {MIN_TOKEN_LENGTH} characters. "
            "Generate one with `openssl rand -hex 32` and put it in .env."
        )
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    import django
    from django.conf import settings

    django.setup()
    if not settings.DEBUG:
        refuse("settings.DEBUG is false; this server runs only in development.")
    return token


def main() -> None:
    """Parse arguments, apply the guards, and serve SSE."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    token = check_environment()

    from django_ai_boost.server_fastmcp import create_auth_provider, register_tools
    from fastmcp import FastMCP
    from starlette.middleware import Middleware
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    server = FastMCP("Django AI Boost Server", auth=create_auth_provider(token))
    register_tools(server)
    server.run(
        transport="sse",
        host=args.host,
        port=args.port,
        middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)],
    )


if __name__ == "__main__":
    main()
