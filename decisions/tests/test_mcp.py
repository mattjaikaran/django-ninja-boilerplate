"""Tests for the decisions MCP tool and its registration."""

import inspect

import pytest

from decisions.mcp import TOOLS, evaluate_decision, gate_agent_action, register
from decisions.services import DecisionService


@pytest.fixture(autouse=True)
def clear_provider_cache():
    """Reset the class-level provider cache around each test."""
    DecisionService._providers.clear()
    yield
    DecisionService._providers.clear()


@pytest.mark.unit
class TestEvaluateDecisionTool:
    """The tool wraps DecisionService and returns plain data."""

    def test_returns_serialisable_result(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        result = evaluate_decision(
            state={"ticket": "T-1"},
            questions={"churn": {"type": "noul", "instructions": "Will they cancel?"}},
        )
        assert result == {
            "answers": {"churn": False},
            "answer_confidence": {"churn": 0.99},
            "confidence": 0.99,
            "provider": "fake",
            "fallback_used": False,
            "escalation_recommended": False,
            "escalated_questions": [],
        }

    def test_unknown_configured_provider_raises(self, settings):
        from api.exceptions import ValidationError

        settings.SYSTEMONE_PROVIDER = "nope"
        with pytest.raises(ValidationError):
            evaluate_decision(state={}, questions={})

    def test_signature_has_no_provider_override(self):
        assert list(inspect.signature(evaluate_decision).parameters) == [
            "state",
            "questions",
        ]


@pytest.mark.unit
class TestAgentTools:
    def test_agent_tools_take_no_provider_or_threshold(self):
        for tool in TOOLS:
            params = set(inspect.signature(tool).parameters)
            assert not params & {"provider", "threshold", "thresholds"}

    def test_gate_tool_returns_the_decision(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        result = gate_agent_action("ls", "local")
        assert (result["pack"], result["provider"]) == ("gate_action", "fake")


@pytest.mark.unit
class TestRegister:
    """Registration is gated by the setting and the optional package."""

    def test_disabled_by_setting(self, settings, monkeypatch):
        tools: list = []
        monkeypatch.setattr("decisions.mcp._boost_tools", lambda: tools)
        settings.ENABLE_DECISION_MCP = False
        assert register() is False
        assert tools == []

    def test_enabled_but_package_missing(self, settings, monkeypatch):
        settings.ENABLE_DECISION_MCP = True
        monkeypatch.setattr("decisions.mcp._boost_tools", lambda: None)
        assert register() is False

    def test_enabled_adds_each_tool_once(self, settings, monkeypatch):
        tools: list = ["existing"]
        monkeypatch.setattr("decisions.mcp._boost_tools", lambda: tools)
        settings.ENABLE_DECISION_MCP = True
        assert register() is True
        assert register() is True
        assert tools == ["existing", *TOOLS]

    def test_real_ai_boost_exposes_a_tool_list(self):
        """Fails when a django-ai-boost upgrade removes the list we append to."""
        pytest.importorskip("django_ai_boost")
        from decisions.mcp import _boost_tools

        tools = _boost_tools()
        assert isinstance(tools, list)
        assert all(callable(tool) for tool in tools)
