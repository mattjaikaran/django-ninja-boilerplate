"""Tests for the deterministic fake provider."""

import pytest

from decisions.providers import FakeProvider
from decisions.schemas import QuestionSchema


@pytest.mark.unit
class TestFakeProvider:
    """The fake provider is deterministic and dependency-free."""

    def test_is_available(self):
        assert FakeProvider().is_available() is True

    def test_choice_returns_first_mapping_criterion(self):
        result = FakeProvider().predict(
            {"any": "state"},
            {
                "risk": {
                    "type": "choice",
                    "instructions": "Approve or deny",
                    "criteria": {"approve": "safe", "deny": "risky"},
                }
            },
        )
        assert result.answers == {"risk": "approve"}
        assert result.answer_confidence == {"risk": 0.99}
        assert result.confidence == 0.99
        assert result.provider == "fake"
        assert result.routing is None
        assert result.fallback_used is False
        assert result.escalation_recommended is False

    def test_choice_returns_first_list_criterion(self):
        result = FakeProvider().predict(
            {},
            {
                "tier": {
                    "type": "choice",
                    "instructions": "Pick a tier",
                    "criteria": ["gold", "silver"],
                }
            },
        )
        assert result.answers == {"tier": "gold"}

    def test_choice_defaults_when_no_criteria(self):
        result = FakeProvider().predict(
            {}, {"risk": {"type": "choice", "instructions": "Approve?"}}
        )
        assert result.answers == {"risk": "approve"}

    def test_score_returns_one(self):
        result = FakeProvider().predict(
            {}, {"severity": {"type": "score", "instructions": "Score 0 to 1"}}
        )
        assert result.answers == {"severity": 1.0}

    def test_noul_returns_false(self):
        result = FakeProvider().predict(
            {}, {"churn": {"type": "noul", "instructions": "Will they cancel?"}}
        )
        assert result.answers == {"churn": False}

    def test_unknown_type_returns_none(self):
        result = FakeProvider().predict(
            {}, {"note": {"type": "mystery", "instructions": "?"}}
        )
        assert result.answers == {"note": None}

    def test_accepts_schema_objects(self):
        question = QuestionSchema(
            type="choice", instructions="Approve?", criteria={"approve": "safe"}
        )
        result = FakeProvider().predict({}, {"risk": question})
        assert result.answers == {"risk": "approve"}

    def test_is_deterministic(self):
        provider = FakeProvider()
        questions = {"risk": {"type": "choice", "instructions": "Approve?"}}
        assert provider.predict({"a": 1}, questions) == provider.predict(
            {"a": 1}, questions
        )

    def test_confidence_is_configurable(self):
        result = FakeProvider(confidence=0.42).predict(
            {}, {"q": {"type": "noul", "instructions": "?"}}
        )
        assert result.confidence == 0.42
        assert result.answer_confidence == {"q": 0.42}

    def test_empty_questions(self):
        result = FakeProvider().predict({}, {})
        assert result.answers == {}
        assert result.confidence == 0.0
