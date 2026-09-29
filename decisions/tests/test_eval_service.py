"""Tests for decision accuracy, calibration, and latency measurement."""

import json

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command

from api.exceptions import ValidationError
from decisions.providers.base import DecisionProvider, DecisionResult
from decisions.services import DecisionEvalService, DecisionService, load_cases
from decisions.services.eval_dataset import benchmark_domains, is_correct
from decisions.services.eval_metrics import (
    Outcome,
    expected_calibration_error,
    percentile,
    recommend_threshold,
    reliability_bins,
    summarise,
)

QUESTIONS = {
    "team": {
        "type": "choice",
        "instructions": "Team?",
        "criteria": {"a": "A", "b": "B"},
    },
    "yes": {"type": "noul", "instructions": "Yes?"},
}


class _ScriptedProvider(DecisionProvider):
    """Return scripted answers and confidences in call order."""

    name = "scripted"

    def __init__(self, script, available=True):
        self.script = list(script)
        self.available = available
        self.calls = 0

    def is_available(self) -> bool:
        return self.available

    def predict(self, state, questions) -> DecisionResult:
        self.calls += 1
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


def _write_dataset(tmp_path, cases, questions=QUESTIONS):
    path = tmp_path / "set.json"
    path.write_text(
        json.dumps({"name": "tiny", "questions": questions, "cases": cases})
    )
    return path


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
            ({"type": "noul"}, True, False, False),
        ],
    )
    def test_is_correct(self, question, answer, expected, correct):
        assert is_correct(question, answer, expected) is correct

    @pytest.mark.parametrize("qtype", ["score", "vote"])
    def test_unscorable_types_are_rejected(self, qtype):
        with pytest.raises(ValidationError):
            is_correct({"type": qtype}, 1.0, 1)

    def test_ece_weights_each_bins_gap(self):
        outcomes = [Outcome("q", i < 8, 0.85) for i in range(10)]
        outcomes += [Outcome("q", i < 3, 0.35) for i in range(10)]
        assert expected_calibration_error(outcomes) == pytest.approx(0.05)

    def test_perfectly_calibrated_bins_have_zero_error(self):
        outcomes = [Outcome("q", i < 8, 0.8) for i in range(10)]
        outcomes += [Outcome("q", i < 3, 0.3) for i in range(10)]
        assert expected_calibration_error(outcomes) == pytest.approx(0.0)

    def test_overconfidence_is_measured(self):
        outcomes = [Outcome("q", False, 0.95) for _ in range(4)]
        assert expected_calibration_error(outcomes) == pytest.approx(0.95)

    def test_confidence_of_one_lands_in_the_last_bin(self):
        (last,) = reliability_bins([Outcome("q", True, 1.0)])
        assert (last.low, last.high, last.count) == (0.9, 1.0, 1)

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

    def test_percentile_uses_nearest_rank(self):
        values = list(range(1, 21))
        assert (percentile(values, 50), percentile(values, 95)) == (10, 19)
        assert percentile([], 50) is None


@pytest.mark.unit
class TestRecommendThreshold:
    def test_picks_the_lowest_threshold_that_meets_the_target(self):
        outcomes = [Outcome("q", False, 0.3) for _ in range(5)]
        outcomes += [Outcome("q", True, 0.6) for _ in range(20)]
        assert recommend_threshold(outcomes, 0.95, 10) == 0.35

    def test_returns_none_when_support_runs_out_first(self):
        outcomes = [Outcome("q", i % 2 == 0, 0.9) for i in range(20)]
        assert recommend_threshold(outcomes, 0.95, 10) is None


@pytest.mark.unit
class TestLoadCases:
    def test_jsonl_uses_sibling_questions_and_filters_by_split(self, tmp_path):
        (tmp_path / "questions.json").write_text(
            json.dumps({"name": "domain", "questions": QUESTIONS})
        )
        lines = [
            {"id": "c1", "split": "dev", "state": {}, "expected": {"team": "a"}},
            {"id": "c2", "split": "test", "state": {}, "expected": {"yes": True}},
        ]
        (tmp_path / "cases.jsonl").write_text("\n".join(json.dumps(x) for x in lines))
        cases = load_cases(tmp_path, split="test")
        assert [(c.case_id, c.dataset, list(c.questions)) for c in cases] == [
            ("c2", "domain", ["yes"])
        ]

    def test_score_questions_are_rejected_before_any_case_is_read(self, tmp_path):
        questions = {**QUESTIONS, "stars": {"type": "score", "instructions": "?"}}
        path = _write_dataset(
            tmp_path, [{"state": {}, "expected": {"team": "a"}}], questions
        )
        with pytest.raises(ValidationError, match="stars"):
            load_cases(path)

    def test_choice_labels_must_be_options(self, tmp_path):
        path = _write_dataset(tmp_path, [{"state": {}, "expected": {"team": "z"}}])
        with pytest.raises(ValidationError, match="not a 'team' option"):
            load_cases(path)

    def test_labels_for_unknown_questions_are_rejected(self, tmp_path):
        path = _write_dataset(tmp_path, [{"state": {}, "expected": {"other": "a"}}])
        with pytest.raises(ValidationError, match="unknown questions"):
            load_cases(path)

    def test_empty_dataset_is_rejected(self, tmp_path):
        with pytest.raises(ValidationError, match="no cases"):
            load_cases(_write_dataset(tmp_path, []))

    def test_bundled_benchmark_loads_with_dev_and_test_splits(self):
        domains = benchmark_domains()
        cases = [case for domain in domains for case in load_cases(domain)]
        assert len(domains) >= 4
        assert len(cases) >= 200
        assert {case.split for case in cases} == {"dev", "test"}


@pytest.mark.unit
class TestDecisionEvalService:
    def test_report_scores_each_question_and_times_each_call(self, tmp_path):
        DecisionService._providers["fake"] = _ScriptedProvider(
            [
                ({"team": "a", "yes": 0.9}, {"team": 0.9, "yes": 0.9}),
                ({"team": "b", "yes": 0.1}, {"team": 0.6, "yes": 0.9}),
            ]
        )
        path = _write_dataset(
            tmp_path,
            [
                {"state": {"t": 1}, "expected": {"team": "a", "yes": True}},
                {"state": {"t": 2}, "expected": {"team": "a", "yes": True}},
            ],
        )
        report = DecisionEvalService(provider="fake").evaluate(load_cases(path))
        assert report.provider == "scripted"
        assert (report.cases, report.overall.accuracy) == (2, 0.5)
        assert report.per_question["team"].accuracy == 0.5
        assert report.per_question["yes"].ece == pytest.approx(0.4)
        assert report.latency.cold_ms is not None
        assert report.latency.warm_count == 1
        assert [o.case_id for o in report.outcomes] == ["tiny-1"] * 2 + ["tiny-2"] * 2

    def test_unavailable_provider_fails_before_any_call(self, tmp_path):
        provider = _ScriptedProvider([], available=False)
        DecisionService._providers["jev"] = provider
        path = _write_dataset(tmp_path, [{"state": {}, "expected": {"team": "a"}}])
        with pytest.raises(ImproperlyConfigured, match="'jev' is not available"):
            DecisionEvalService(provider="jev").evaluate(load_cases(path))
        assert provider.calls == 0

    def test_cost_uses_the_configured_price(self, tmp_path, settings):
        settings.DECISION_PROVIDER_COSTS = {"scripted": 0.01}
        DecisionService._providers["fake"] = _ScriptedProvider(
            [({"team": "a"}, {"team": 0.9})] * 3
        )
        cases = [{"state": {}, "expected": {"team": "a"}}] * 3
        report = DecisionEvalService(provider="fake").evaluate(
            load_cases(_write_dataset(tmp_path, cases))
        )
        assert report.total_cost == pytest.approx(0.03)


@pytest.mark.unit
class TestEvalCommand:
    def test_bundled_dataset_runs_with_the_fake_provider(self, capsys):
        call_command("eval_decisions", "--provider", "fake", "--json")
        report = json.loads(capsys.readouterr().out)
        assert report["status"] == "ok"
        assert report["cases"] == 40
        assert set(report["per_question"]) == {"team", "angry", "wants_refund"}

    def test_benchmark_runs_every_domain(self, capsys):
        call_command("eval_decisions", "--benchmark", "--provider", "fake", "--json")
        report = json.loads(capsys.readouterr().out)
        assert set(report["per_dataset"]) == {p.name for p in benchmark_domains()}

    def test_unavailable_jev_fails_without_the_skip_flag(self, settings):
        settings.TYPESAFE_API_KEY = ""
        with pytest.raises(CommandError, match="not available"):
            call_command("eval_decisions", "--provider", "jev")

    def test_unavailable_jev_is_recorded_as_skipped_not_replaced(
        self, settings, tmp_path
    ):
        settings.TYPESAFE_API_KEY = ""
        output = tmp_path / "jev.json"
        call_command(
            "eval_decisions",
            "--provider",
            "jev",
            "--skip-unavailable",
            "--output",
            str(output),
        )
        report = json.loads(output.read_text())
        assert (report["status"], report["provider"]) == ("skipped", "jev")
        assert "outcomes" not in report
