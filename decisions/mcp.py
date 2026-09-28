"""MCP tool for the decisions app.

``evaluate_decision`` wraps :meth:`DecisionService.decide` so an MCP client
can ask the decision engine questions. MCP support is off unless
``ENABLE_DECISION_MCP`` is true, and it needs the ``django-ai-boost`` package
from the ``dev`` extra.

django-ai-boost calls ``django.setup()`` before it registers its tool list,
so :func:`register`, which runs from ``DecisionsConfig.ready()``, appends
this tool to that list in time for the server to expose it.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from django.conf import settings

from decisions.services import DecisionService

logger = logging.getLogger(__name__)

#: Name of the MCP tool that evaluates a decision.
EVALUATE_TOOL_NAME = "evaluate_decision"


def _boost_tools() -> list[Any] | None:
    """Return django-ai-boost's registered tool list, or ``None`` if absent."""
    try:
        server = importlib.import_module("django_ai_boost.server_fastmcp")
    except ImportError:
        return None
    return server.TOOLS


def evaluate_decision(
    state: dict[str, Any],
    questions: dict[str, Any],
) -> dict[str, Any]:
    """Answer *questions* from *state* with the configured provider.

    MCP clients cannot choose a provider; ``SYSTEMONE_PROVIDER`` decides.

    Args:
        state: Structured input for the decision.
        questions: Mapping of question key to a question definition.

    Returns:
        A dictionary with ``answers``, ``confidence``, ``provider``,
        ``fallback_used``, and ``escalation_recommended`` keys.
    """
    result = DecisionService().decide(state=state, questions=questions)
    return {
        "answers": result.answers,
        "confidence": result.confidence,
        "provider": result.provider,
        "fallback_used": result.fallback_used,
        "escalation_recommended": result.escalation_recommended,
    }


def register() -> bool:
    """Add ``evaluate_decision`` to the django-ai-boost server, when enabled.

    Returns:
        ``True`` when the tool is registered, otherwise ``False``.
    """
    if not getattr(settings, "ENABLE_DECISION_MCP", False):
        return False
    tools = _boost_tools()
    if tools is None:
        logger.warning(
            "ENABLE_DECISION_MCP is true but django-ai-boost is not installed. "
            "Install it with `uv sync --extra dev`."
        )
        return False
    if evaluate_decision not in tools:
        tools.append(evaluate_decision)
    logger.info("Decision MCP tool registered: %s", EVALUATE_TOOL_NAME)
    return True
