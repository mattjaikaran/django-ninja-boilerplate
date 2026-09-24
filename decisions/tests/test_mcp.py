"""Tests for the optional MCP tool wrappers."""

import pytest

from decisions.mcp import EVALUATE_TOOL_NAME, evaluate_decision, get_tools, register
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
            provider="fake",
        )
        assert result == {
            "answers": {"churn": False},
            "confidence": 0.99,
            "provider": "fake",
            "fallback_used": False,
            "escalation_recommended": False,
        }

    def test_unknown_provider_raises(self):
        from api.exceptions import ValidationError

        with pytest.raises(ValidationError):
            evaluate_decision(state={}, questions={}, provider="nope")


@pytest.mark.unit
class TestGetTools:
    """Tool definitions carry a name, schema, and callable handler."""

    def test_shape(self):
        tools = get_tools()
        assert len(tools) == 1
        tool = tools[0]
        assert tool["name"] == EVALUATE_TOOL_NAME
        assert tool["handler"] is evaluate_decision
        assert tool["input_schema"]["required"] == ["state", "questions"]


@pytest.mark.unit
class TestRegister:
    """Registration is gated by the setting and the optional package."""

    def test_disabled_by_setting(self, settings):
        settings.ENABLE_DECISION_MCP = False
        assert register() is False

    def test_enabled_but_package_missing(self, settings, monkeypatch):
        settings.ENABLE_DECISION_MCP = True
        monkeypatch.setattr("decisions.mcp._boost_installed", lambda: False)
        assert register() is False

    def test_enabled_with_package(self, settings, monkeypatch):
        settings.ENABLE_DECISION_MCP = True
        monkeypatch.setattr("decisions.mcp._boost_installed", lambda: True)
        assert register() is True
