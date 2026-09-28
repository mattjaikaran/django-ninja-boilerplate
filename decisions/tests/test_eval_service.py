"""Tests for decision accuracy and calibration measurement."""

import json
from pathlib import Path

import pytest
from django.core.management import call_command

from api.exceptions import ValidationError
from decisions.providers.base import DecisionProvider, DecisionResult
from decisions.services import DecisionEvalService, DecisionService
from decisions.services.eval_service import (
    Outcome,
    expected_calibration_error,
    is_correct,
    summarise,
)

QUESTIONS = {
    "team": {"type": "choice", "instructions": "Team?", "criteria": {"a": "A"}},
    "yes": {"type": "noul", "instructions": "Yes?"},
}


class _ScriptedProvider(DecisionProvider):
    """Return scripted answers and confidences in call order."""

    name = "scripted"

    def __init__(self, script):
        self.script = list(script)

    def is_available(self) -> bool:
        return True

    def predict(self, state, questions) -> DecisionResult:
        answers, confidences = self.script.pop(0)
        return DecisionResult(
            answers={k: answers[k] for k in questions},
            answer_confidence={k: confidences[k] for k in questions},
            confidence=min(confidences[k] for k in questions),
            provider=self.name,
        )


@pytest.fixture(autouse=True)
def clear_provider_cache():
    DecisionService._providers.clear()
    yield
    DecisionService._providers.clear()


@pytest.mark.unit
class TestScoring:
    @pytest.mark.parametrize(
        ("question", "answer", "expected", "correct"),
        [
            ({"type": "choice"}, "a", "a", True),
            ({"type": "choice"}, "b", "a", False),
            ({"type": "noul"}, 0.8, True, True),
            ({"type": "noul"}, 0.2, True, False),
            ({"type": "noul"}, 0.5, True, True),
            ({"type": "noul"}, False, False, True),
            ({"type": "score"}, 1.4, 1, True),
            ({"type": "score"}, 1.6, 1, False),
        ],
    )
    def test_is_correct(self, question, answer, expected, correct):
        assert is_correct(question, answer, expected) is correct

    def test_unknown_type_is_rejected(self):
        with pytest.raises(ValidationError):
            is_correct({"type": "vote"}, "a", "a")

    def test_perfectly_calibrated_bins_have_zero_error(self):
        outcomes = [Outcome("q", i < 8, 0.85) for i in range(10)]
        outcomes += [Outcome("q", i < 3, 0.35) for i in range(10)]
        assert expected_calibration_error(outcomes) == pytest.approx(0.05)

    def test_overconfidence_is_measured(self):
        outcomes = [Outcome("q", False, 0.95) for _ in range(4)]
        assert expected_calibration_error(outcomes) == pytest.approx(0.95)

    def test_threshold_rows_report_coverage_and_accuracy(self):
        outcomes = [
            Outcome("q", True, 0.95),
            Outcome("q", False, 0.75),
            Outcome("q", True, 0.55),
            Outcome("q", False, 0.40),
        ]
        rows = {
            r.threshold: r for r in summarise(outcomes, (0.5, 0.9, 0.99)).thresholds
        }
        assert (rows[0.5].coverage, rows[0.5].accuracy) == (0.75, pytest.approx(2 / 3))
        assert (rows[0.9].coverage, rows[0.9].accuracy) == (0.25, 1.0)
        assert (rows[0.99].coverage, rows[0.99].accuracy) == (0.0, None)


@pytest.mark.unit
class TestDecisionEvalService:
    def test_report_scores_each_question(self):
        DecisionService._providers["fake"] = _ScriptedProvider(
            [
                ({"team": "a", "yes": 0.9}, {"team": 0.9, "yes": 0.9}),
                ({"team": "b", "yes": 0.1}, {"team": 0.6, "yes": 0.9}),
            ]
        )
        dataset = {
            "name": "tiny",
            "questions": QUESTIONS,
            "cases": [
                {"state": {"t": 1}, "expected": {"team": "a", "yes": True}},
                {"state": {"t": 2}, "expected": {"team": "a", "yes": True}},
            ],
        }
        report = DecisionEvalService(provider="fake").evaluate(dataset)
        assert report.provider == "scripted"
        assert report.cases == 2
        assert report.overall.accuracy == 0.5
        assert report.per_question["team"].accuracy == 0.5
        assert report.per_question["yes"].accuracy == 0.5
        assert report.per_question["yes"].ece == pytest.approx(0.4)

    def test_labels_for_unknown_questions_are_rejected(self):
        dataset = {
            "questions": QUESTIONS,
            "cases": [{"state": {}, "expected": {"other": "a"}}],
        }
        with pytest.raises(ValidationError, match="unknown questions"):
            DecisionEvalService(provider="fake").evaluate(dataset)

    def test_empty_dataset_is_rejected(self):
        with pytest.raises(ValidationError, match="no cases"):
            DecisionEvalService(provider="fake").evaluate({"cases": []})


@pytest.mark.unit
def test_command_runs_the_bundled_dataset_with_the_fake_provider(capsys):
    call_command("eval_decisions", "--provider", "fake", "--json")
    report = json.loads(capsys.readouterr().out)
    bundled = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/eval/support_tickets.json"
        ).read_text()
    )
    assert report["cases"] == len(bundled["cases"])
    assert set(report["per_question"]) == set(bundled["questions"])
