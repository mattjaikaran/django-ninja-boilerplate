"""Optional MCP tool definitions for the decisions app.

The tools wrap :meth:`DecisionService.decide` so an MCP client can ask the
decision engine questions. MCP support is off unless ``ENABLE_DECISION_MCP``
is true, and it needs the ``django-ai-boost`` extra.

The handlers are plain functions with no MCP dependency, so they are
importable and testable even when MCP support is not installed.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any

from django.conf import settings

from decisions.services import DecisionService

logger = logging.getLogger(__name__)


def _boost_installed() -> bool:
    """Return ``True`` when the ``django_ai_boost`` package is importable."""
    try:
        return importlib.util.find_spec("django_ai_boost") is not None
    except (ImportError, ValueError):
        return False


#: Name of the MCP tool that evaluates a decision.
EVALUATE_TOOL_NAME = "evaluate_decision"


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


def get_tools() -> list[dict[str, Any]]:
    """Return the MCP tool definitions for this app.

    Returns:
        A list of tool definitions, each with ``name``, ``description``,
        ``input_schema``, and ``handler`` keys.
    """
    return [
        {
            "name": EVALUATE_TOOL_NAME,
            "description": (
                "Answer a set of questions using the System One decision engine."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "state": {"type": "object"},
                    "questions": {"type": "object"},
                },
                "required": ["state", "questions"],
                "additionalProperties": False,
            },
            "handler": evaluate_decision,
        }
    ]


def register() -> bool:
    """Register the decision tools with the MCP server, when enabled.

    Returns:
        ``True`` when the tools were registered, otherwise ``False``.
    """
    if not getattr(settings, "ENABLE_DECISION_MCP", False):
        return False
    if not _boost_installed():
        logger.warning(
            "ENABLE_DECISION_MCP is true but django-ai-boost is not installed. "
            "Install it with `uv sync --extra dev`."
        )
        return False
    logger.info("Decision MCP tools are available: %s", EVALUATE_TOOL_NAME)
    return True
