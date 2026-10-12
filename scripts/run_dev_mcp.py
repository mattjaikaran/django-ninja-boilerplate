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

On top of the django-ai-boost tools, the server registers four read-only
project tools that reuse the CLI scripts by import:

- ``tickets_next``: claimable small tickets (``scripts/tickets.py next``).
- ``tickets_show``: one ticket with its claim blockers (``tickets.py show``).
- ``journeys_report``: journey counts, errors, and gaps (``check_journeys``).
- ``agent_status``: the ``scripts/agent_status.py --json`` summary.

Claims come from local ``agent/*`` branches and ``origin`` remote-tracking
refs, so the tools never contact the remote. Run ``git fetch`` for fresh
claims. Claiming a ticket stays a shell action: ``just tickets claim T-NNN``.

Usage:
    python scripts/run_dev_mcp.py [--host 0.0.0.0] [--port 8001]

Exit: 2 = a guard refused to start
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from journeys.services import Issue

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
SCRIPTS_DIR = str(Path(__file__).resolve().parent)
READ_ONLY = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}
CLAIM_HINT = "Claim in a shell: just tickets claim <id>"

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
    for entry in (PROJECT_ROOT, SCRIPTS_DIR):
        if entry not in sys.path:
            sys.path.insert(0, entry)

    import django
    from django.conf import settings

    django.setup()
    if not settings.DEBUG:
        refuse("settings.DEBUG is false; this server runs only in development.")
    return token


def _claims() -> set[str]:
    """Return ticket ids claimed by local refs, without contacting the remote."""
    import agent_status as status_script

    return status_script.local_claims()


def _issue(issue: Issue) -> str:
    """Format a journeys finding like ``scripts/check_journeys.py`` does."""
    where = f" ({issue.path})" if issue.path else ""
    return f"{issue.code}: {issue.message}{where}"


def tickets_next() -> dict[str, Any]:
    """List claimable small tickets: ready, dependencies done, no claim overlap.

    Claims come from local agent/* branches and origin remote-tracking refs.
    Run `git fetch` first for fresh claims. Claim in a shell with
    `just tickets claim <id>`; this server cannot claim.
    """
    import tickets

    board = tickets.load_board(tickets.tickets_dir())
    if board.errors:
        return {
            "tickets": [],
            "board_errors": board.errors,
            "hint": "Fix the board first: just tickets check",
        }
    claimed = _claims()
    rows = [
        {"id": ticket.id, "title": ticket.title, "branch": ticket.branch}
        for ticket in (board.tickets[key] for key in sorted(board.tickets))
        if ticket.tier == "small" and not tickets.blockers(ticket, board, claimed)
    ]
    return {"tickets": rows, "claimed": sorted(claimed), "hint": CLAIM_HINT}


def tickets_show(ticket_id: str) -> dict[str, Any]:
    """Return one ticket file (for example T-001) and why it is not claimable.

    ``claimable`` is null when the board has validation errors.
    """
    import tickets
    from fastmcp.exceptions import ToolError

    board = tickets.load_board(tickets.tickets_dir())
    ticket = board.tickets.get(ticket_id)
    if ticket is None:
        details = "; ".join(board.errors)
        raise ToolError(f"{ticket_id} not found or invalid. {details}".strip())
    result: dict[str, Any] = {
        "id": ticket.id,
        "path": tickets.display(ticket.path),
        "text": ticket.path.read_text(encoding="utf-8").rstrip(),
    }
    if board.errors:
        return {**result, "claimable": None, "board_errors": board.errors}
    reasons = tickets.blockers(ticket, board, _claims())
    if reasons:
        return {**result, "claimable": False, "blockers": reasons}
    hint = CLAIM_HINT.replace("<id>", ticket.id)
    return {**result, "claimable": True, "blockers": [], "hint": hint}


def journeys_report() -> dict[str, Any]:
    """Summarize the journeys gate: counts, then every error and gap.

    Warnings are counted only. Run `just check-journeys` for the full text.
    """
    from journeys.services import build_report, spec_paths

    report = build_report(spec_paths(Path(PROJECT_ROOT)))
    return {
        "ok": report.ok,
        "features": len(report.features),
        "journeys": len(report.journeys),
        "verified": report.verified_journeys,
        "warnings": len(report.warnings),
        "e2e_dir": report.e2e_dir_exists,
        "e2e_report": report.report_exists,
        "errors": [_issue(issue) for issue in report.errors],
        "gaps": [_issue(issue) for issue in report.gaps],
    }


def agent_status() -> dict[str, Any]:
    """Return the session summary: git, tickets, journeys, gauntlet, OpenAPI.

    Same data as `just agent-status --json`.
    """
    import agent_status as status_script

    return status_script.collect()


def register_project_tools(server: FastMCP) -> None:
    """Register the read-only project tools on *server*."""
    for fn in (tickets_next, tickets_show, journeys_report, agent_status):
        server.tool(fn, annotations=READ_ONLY)


def build_server(token: str) -> FastMCP:
    """Build the server: django-ai-boost tools plus the project tools."""
    from django_ai_boost.server_fastmcp import create_auth_provider, register_tools
    from fastmcp import FastMCP

    server = FastMCP("Django AI Boost Server", auth=create_auth_provider(token))
    register_tools(server)
    register_project_tools(server)
    return server


def main() -> None:
    """Parse arguments, apply the guards, and serve SSE."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    token = check_environment()

    from starlette.middleware import Middleware
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    server = build_server(token)
    server.run(
        transport="sse",
        host=args.host,
        port=args.port,
        middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)],
    )


if __name__ == "__main__":
    main()
