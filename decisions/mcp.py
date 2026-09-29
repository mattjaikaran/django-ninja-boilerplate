"""MCP tools for the decisions app.

``evaluate_decision`` wraps :meth:`DecisionService.decide` so an MCP client
can ask the decision engine questions. Four agent tools wrap
:class:`AgentDecisionService`: ``route_agent_task``, ``triage_change``,
``gate_agent_action``, and ``pick_generator``. They answer cheap, typed
questions locally, so an agent can skip a large-model call when the answer
meets its threshold, and escalate when it does not.

MCP clients cannot choose a provider or a threshold; ``SYSTEMONE_PROVIDER``
and ``DECISION_THRESHOLDS_FILE`` decide. MCP support is off unless
``ENABLE_DECISION_MCP`` is true, and it needs the ``django-ai-boost`` package
from the ``dev`` extra.

django-ai-boost calls ``django.setup()`` before it registers its tool list,
so :func:`register`, which runs from ``DecisionsConfig.ready()``, appends
these tools to that list in time for the server to expose them.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from django.conf import settings

from decisions.services import DecisionService
from decisions.services.agent_service import AgentDecisionService

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

    Args:
        state: Structured input for the decision.
        questions: Mapping of question key to a question definition.

    Returns:
        A dictionary with ``answers``, ``answer_confidence``, ``confidence``,
        ``provider``, ``fallback_used``, ``escalation_recommended``, and
        ``escalated_questions`` keys.
    """
    result = DecisionService().decide(state=state, questions=questions)
    return {
        "answers": result.answers,
        "answer_confidence": result.answer_confidence,
        "confidence": result.confidence,
        "provider": result.provider,
        "fallback_used": result.fallback_used,
        "escalation_recommended": result.escalation_recommended,
        "escalated_questions": list(result.escalated_questions),
    }


def route_agent_task(task: str, files_hint: str = "") -> dict[str, Any]:
    """Pick the cheapest capable model tier for a coding task.

    ``next_step`` is ``use_local``, ``use_mid``, ``use_frontier``,
    ``ask_human``, or ``escalate`` (the local answer is too weak; decide with
    a stronger model).
    """
    return AgentDecisionService().route_task(task, files_hint).as_dict()


def triage_change(
    title: str,
    description: str = "",
    files: list[str] | None = None,
    additions: int = 0,
    deletions: int = 0,
) -> dict[str, Any]:
    """Classify a PR or commit; ``next_step`` is the review depth or ``escalate``."""
    decision = AgentDecisionService().triage_change(
        title, description, files, additions, deletions
    )
    return decision.as_dict()


def gate_agent_action(
    action: str, environment: str = "local", reason: str = ""
) -> dict[str, Any]:
    """Decide whether an agent may run *action* without human approval.

    ``next_step`` is ``allow`` or ``ask_human``. An uncertain answer asks a
    human. Never treat ``allow`` as permission for production or
    irreversible actions that your own policy forbids.
    """
    return AgentDecisionService().gate_action(action, environment, reason).as_dict()


def pick_generator(request: str, app_name: str = "") -> dict[str, Any]:
    """Pick the ``generate_feature`` generator; ``details.command`` is the command."""
    return AgentDecisionService().pick_generator(request, app_name).as_dict()


#: Every tool this module registers, in registration order.
TOOLS = (
    evaluate_decision,
    route_agent_task,
    triage_change,
    gate_agent_action,
    pick_generator,
)


def register() -> bool:
    """Add the decision tools to the django-ai-boost server, when enabled.

    Returns:
        ``True`` when the tools are registered, otherwise ``False``.
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
    for tool in TOOLS:
        if tool not in tools:
            tools.append(tool)
    logger.info(
        "Decision MCP tools registered: %s", ", ".join(t.__name__ for t in TOOLS)
    )
    return True
