"""Contract test for the dev MCP server (scripts/run_dev_mcp.py).

Builds the server in process the way ``main`` does, then talks to it over
fastmcp's in-memory transport: no network, no Docker.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastmcp", reason="fastmcp ships in the dev extra")
pytest.importorskip("django_ai_boost", reason="django-ai-boost ships in the dev extra")

from fastmcp import Client

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
_spec = importlib.util.spec_from_file_location(
    "run_dev_mcp", _SCRIPTS / "run_dev_mcp.py"
)
assert _spec is not None
assert _spec.loader is not None
run_dev_mcp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_dev_mcp)

PROJECT_TOOLS = {"tickets_next", "tickets_show", "journeys_report", "agent_status"}


def _exercise() -> tuple[dict, dict, dict]:
    server = run_dev_mcp.build_server("x" * run_dev_mcp.MIN_TOKEN_LENGTH)

    async def go() -> tuple[dict, dict, dict]:
        async with Client(server) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            nxt = await client.call_tool("tickets_next", {})
            status = await client.call_tool("agent_status", {})
            return tools, nxt.data, status.data

    return asyncio.run(go())


def test_project_tools_are_read_only_and_answer_with_their_contract():
    tools, nxt, status = _exercise()

    assert tools.keys() >= PROJECT_TOOLS
    for name in PROJECT_TOOLS:
        hints = tools[name].annotations
        assert hints is not None, name
        assert hints.readOnlyHint is True, name
        assert hints.idempotentHint is True, name
        assert hints.openWorldHint is False, name
    # django-ai-boost's own tools are registered alongside ours.
    assert len(tools) > len(PROJECT_TOOLS)

    assert isinstance(nxt["tickets"], list)
    assert "hint" in nxt
    if "board_errors" not in nxt:
        assert isinstance(nxt["claimed"], list)
        for row in nxt["tickets"]:
            assert set(row) == {"id", "title", "branch"}

    assert set(status) == {"git", "tickets", "journeys", "gauntlet", "openapi"}
