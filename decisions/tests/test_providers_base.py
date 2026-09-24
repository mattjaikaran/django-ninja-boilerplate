"""Tests for the provider base helpers."""

import pytest

from decisions.providers import aggregate_confidence, result_from_raw


class _Response:
    """Object-shaped provider response, as a vendor SDK might return."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.mark.unit
class TestAggregateConfidence:
    """The aggregate is the weakest answer."""

    def test_minimum_wins(self):
        assert aggregate_confidence([0.94, 0.71, 0.88]) == 0.71

    def test_single_value(self):
        assert aggregate_confidence([0.42]) == 0.42

    def test_empty_is_zero(self):
        assert aggregate_confidence([]) == 0.0


@pytest.mark.unit
class TestResultFromRaw:
    """Provider responses normalise to a DecisionResult."""

    def test_typed_answers_and_per_answer_confidence(self):
        raw = {
            "answers": {
                "department": {"choice": "billing", "confidence": 0.94},
                "urgency": {"score": 0.8, "confidence": 0.71},
                "churn_risk": {"noul": True, "confidence": 0.88},
            },
            "routing": {"model": "english", "reason": "Latin script"},
        }
        result = result_from_raw(raw, "laya")
        assert result.answers == {
            "department": "billing",
            "urgency": 0.8,
            "churn_risk": True,
        }
        assert result.answer_confidence == {
            "department": 0.94,
            "urgency": 0.71,
            "churn_risk": 0.88,
        }
        assert result.confidence == 0.71
        assert result.routing == {"model": "english", "reason": "Latin script"}
        assert result.provider == "laya"

    def test_bare_value_entry_has_no_confidence(self):
        result = result_from_raw({"answers": {"q": "approve"}}, "fake")
        assert result.answers == {"q": "approve"}
        assert result.answer_confidence == {"q": 0.0}
        assert result.confidence == 0.0

    def test_unknown_value_key_is_kept_as_a_mapping(self):
        raw = {"answers": {"q": {"label": "x", "confidence": 0.5}}}
        result = result_from_raw(raw, "fake")
        assert result.answers == {"q": {"label": "x"}}
        assert result.answer_confidence == {"q": 0.5}

    def test_empty_response(self):
        result = result_from_raw({}, "fake")
        assert result.answers == {}
        assert result.confidence == 0.0
        assert result.routing is None
        assert result.fallback_used is False

    def test_object_response(self):
        raw = _Response(answers={"q": {"choice": "a", "confidence": 0.3}})
        result = result_from_raw(raw, "jev")
        assert result.answers == {"q": "a"}
        assert result.provider == "jev"

    def test_explicit_provider_and_flags_win(self):
        raw = {
            "answers": {"q": {"choice": "a", "confidence": 0.9}},
            "provider": "laya",
            "fallback_used": True,
            "escalation_recommended": True,
        }
        result = result_from_raw(raw, "jev")
        assert result.provider == "laya"
        assert result.fallback_used is True
        assert result.escalation_recommended is True
