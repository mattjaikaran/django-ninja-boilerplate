"""App-level, read-only MCP server over selected Ninja GET routes.

``api/asgi.py`` mounts it at ``/api/mcp`` when ``MCP_ENABLED`` is true. It is
separate from the dev-only `mcp` Compose profile (django-ai-boost), which
exposes the Django project to a coding agent; this one serves your users.

- Auth: every MCP request needs ``Authorization: Bearer <JWT access token>``
  (from ``POST /api/token/pair``). Without a valid token the SDK answers 401
  before any tool runs.
- Tools: one per operationId in ``MCP_TOOLS``. Only GET operations are
  accepted; startup fails on any other method or an unknown id.
- A tool call replays the GET through the full Django stack in-process, with
  the caller's token. Ninja auth, user scoping, throttling and audit logging
  apply as for any API client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from ninja_jwt.exceptions import TokenError
from ninja_jwt.settings import api_settings
from ninja_jwt.tokens import AccessToken as JWTAccessToken
from pydantic import AnyHttpUrl

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.types import ASGIApp, Receive, Scope, Send

MCP_PATH = "/api/mcp"
_METADATA_PREFIX = "/.well-known/oauth-protected-resource"
# Request headers copied to the replayed GET so Django sees the real client.
_FORWARDED_HEADERS = ("host", "x-forwarded-for", "x-forwarded-proto")


class JWTTokenVerifier:
    """Accept the API's own JWT access tokens (ninja-jwt)."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = await sync_to_async(JWTAccessToken)(token)
        except TokenError:
            return None
        return AccessToken(
            token=token,
            client_id=str(claims.get(api_settings.USER_ID_CLAIM)),
            scopes=[],
            expires_at=claims.get("exp"),
        )


def _select_operations(schema: dict[str, Any]) -> list[tuple[str, str, dict]]:
    """Return (operationId, path, operation) for each id in MCP_TOOLS."""
    found: dict[str, tuple[str, dict]] = {}
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            op_id = operation.get("operationId")
            if op_id not in settings.MCP_TOOLS:
                continue
            if method != "get":
                raise ImproperlyConfigured(
                    f"MCP_TOOLS: {op_id} is {method.upper()} {path}. The MCP "
                    "server exposes read-only GET routes only."
                )
            found[op_id] = (path, operation)
    missing = sorted(set(settings.MCP_TOOLS) - found.keys())
    if missing:
        raise ImproperlyConfigured(f"MCP_TOOLS: unknown operationIds {missing}.")
    return [(op_id, *found[op_id]) for op_id in settings.MCP_TOOLS]


def _make_tool(
    django_app: ASGIApp, path: str, operation: dict
) -> tuple[Callable[..., Awaitable[str]], str]:
    params = operation.get("parameters", [])
    path_params = [p["name"] for p in params if p["in"] == "path"]
    query_params = [p["name"] for p in params if p["in"] == "query"]

    async def call_route(ctx: Context, arguments: dict[str, Any] | None = None) -> str:
        token = get_access_token()
        if token is None:
            raise ToolError("Not authenticated.")
        args = dict(arguments or {})
        url = path
        for name in path_params:
            if name not in args:
                raise ToolError(f"Missing path parameter: {name}")
            url = url.replace(f"{{{name}}}", quote(str(args.pop(name)), safe=""))
        unknown = sorted(set(args) - set(query_params))
        if unknown:
            raise ToolError(f"Unknown parameters: {unknown}")

        request = ctx.request_context.request
        headers = {"authorization": f"Bearer {token.token}"}
        headers.update(
            {k: v for k in _FORWARDED_HEADERS if (v := request.headers.get(k))}
        )
        base_url = f"{request.url.scheme}://{headers.get('host', 'localhost')}"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=django_app), base_url=base_url
        ) as client:
            response = await client.get(url, params=args, headers=headers)
        if response.status_code >= 400:
            raise ToolError(f"{response.status_code}: {response.text}")
        return response.text

    lines = [operation.get("summary", ""), operation.get("description", "")]
    if path_params or query_params:
        lines.append(
            "Pass parameters in `arguments`. "
            f"Required: {path_params or 'none'}. Optional: {query_params or 'none'}."
        )
    description = "\n\n".join(line for line in lines if line)
    return call_route, description


def build_mcp_server(django_app: ASGIApp) -> FastMCP:
    """Create the MCP server with one read-only tool per MCP_TOOLS entry."""
    from api.urls import api

    base_url = settings.MCP_BASE_URL.rstrip("/")
    server = FastMCP(
        name="django-ninja-boilerplate",
        instructions="Read-only access to this API as the authenticated user.",
        token_verifier=JWTTokenVerifier(),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(base_url),
            resource_server_url=AnyHttpUrl(f"{base_url}{MCP_PATH}"),
        ),
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        # The SDK's DNS-rebinding check would reject every non-localhost Host.
        # Bearer auth already blocks rebinding (a browser cannot add the
        # header), and Django validates Host on each replayed request.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
    for op_id, path, operation in _select_operations(api.get_openapi_schema()):
        tool, description = _make_tool(django_app, path, operation)
        server.add_tool(
            tool,
            name=op_id,
            description=description,
            annotations=read_only,
            # The route's JSON is the text content; no duplicate wrapper.
            structured_output=False,
        )
    return server


def with_mcp(django_app: ASGIApp) -> ASGIApp:
    """Route MCP paths and the ASGI lifespan to the MCP app, the rest to Django."""
    mcp_app = build_mcp_server(django_app).streamable_http_app()

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope["type"] == "lifespan"
            or path == MCP_PATH
            or path.startswith((f"{MCP_PATH}/", _METADATA_PREFIX))
        ):
            await mcp_app(scope, receive, send)
        else:
            await django_app(scope, receive, send)

    return application
