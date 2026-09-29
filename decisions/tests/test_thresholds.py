"""Tests for server-side per-question escalation thresholds."""

import json

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command

from core.tests.factories import UserFactory
from decisions.services import DecisionService
from decisions.services.eval_metrics import Outcome

QUESTIONS = {
    "team": {"type": "choice", "instructions": "Team?", "criteria": {"a": "A"}},
    "urgent": {"type": "noul", "instructions": "Urgent?"},
}


@pytest.fixture(autouse=True)
def clear_provider_cache():
    DecisionService._providers.clear()
    yield
    DecisionService._providers.clear()


@pytest.fixture
def thresholds_file(tmp_path, settings):
    path = tmp_path / "thresholds.json"
    settings.DECISION_THRESHOLDS_FILE = str(path)
    settings.DECISION_ESCALATION_THRESHOLD = 0.5
    return path


@pytest.mark.unit
class TestEscalationPolicy:
    def test_question_threshold_overrides_the_global_fallback(self, thresholds_file):
        thresholds_file.write_text(json.dumps({"fake": {"team": 0.995}}))
        result = DecisionService(provider="fake").decide({}, QUESTIONS)
        assert result.escalated_questions == ("team",)
        assert result.escalation_recommended is True

    def test_other_providers_sections_do_not_apply(self, thresholds_file):
        thresholds_file.write_text(json.dumps({"laya": {"team": 0.995}}))
        result = DecisionService(provider="fake").decide({}, QUESTIONS)
        assert (result.escalated_questions, result.escalation_recommended) == (
            (),
            False,
        )

    def test_global_threshold_applies_without_a_file(self, settings):
        settings.DECISION_THRESHOLDS_FILE = ""
        settings.DECISION_ESCALATION_THRESHOLD = 0.999
        result = DecisionService(provider="fake").decide({}, QUESTIONS)
        assert result.escalated_questions == ("team", "urgent")

    def test_an_empty_request_is_never_escalated(self, thresholds_file):
        thresholds_file.write_text(json.dumps({"fake": {"team": 1.0}}))
        result = DecisionService(provider="fake").decide({}, {})
        assert result.escalation_recommended is False

    @pytest.mark.parametrize(
        "content",
        ["not json", '["laya"]', '{"fake": {"team": 1.5}}', '{"fake": {"team": true}}'],
    )
    def test_invalid_files_fail_loud(self, thresholds_file, content):
        thresholds_file.write_text(content)
        with pytest.raises(ImproperlyConfigured):
            DecisionService(provider="fake").decide({}, QUESTIONS)

    def test_a_missing_file_fails_loud(self, thresholds_file):
        with pytest.raises(ImproperlyConfigured, match="cannot be read"):
            DecisionService(provider="fake").decide({}, QUESTIONS)


@pytest.mark.django_db
def test_clients_cannot_send_thresholds(api_client, settings):
    from ninja_jwt.tokens import RefreshToken

    settings.SYSTEMONE_PROVIDER = "fake"
    token = RefreshToken.for_user(UserFactory()).access_token
    response = api_client.post(
        "/api/decisions/evaluate",
        data=json.dumps(
            {"state": {}, "questions": QUESTIONS, "thresholds": {"team": 0.0}}
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 422


def _report(tmp_path, outcomes, provider="laya"):
    path = tmp_path / f"{provider}.json"
    path.write_text(
        json.dumps(
            {
                "status": "ok",
                "provider": provider,
                "cases": len(outcomes),
                "latency": {"cold_ms": 900.0, "p50_ms": 40.0, "p95_ms": 60.0},
                "cost_per_call": None,
                "total_cost": None,
                "outcomes": [o.as_dict() for o in outcomes],
            }
        )
    )
    return path


@pytest.mark.unit
class TestRecommendCommand:
    @staticmethod
    def _outcomes(test_wrong=0):
        dev = [Outcome("team", False, 0.2, split="dev") for _ in range(3)]
        dev += [Outcome("team", True, 0.7, split="dev") for _ in range(12)]
        test = [Outcome("team", True, 0.7, split="test") for _ in range(12)]
        test += [Outcome("team", False, 0.7, split="test") for _ in range(test_wrong)]
        test += [Outcome("team", False, 0.1, split="test")]
        return dev + test

    def test_a_threshold_that_held_on_test_is_written_at_the_default_floor(
        self, tmp_path, capsys, settings
    ):
        settings.DECISION_ESCALATION_THRESHOLD = 0.5
        target = tmp_path / "thresholds.json"
        target.write_text(json.dumps({"clm": {"team": 0.9}}))
        report = _report(tmp_path, self._outcomes())
        call_command("recommend_thresholds", str(report), "--write", str(target))
        out = capsys.readouterr().out
        assert "| team | 0.50 | 0.50 | held | 15 | 13 | 12 | 100.0% |" in out
        assert json.loads(target.read_text()) == {
            "clm": {"team": 0.9},
            "laya": {"team": 0.5},
        }

    def test_below_default_needs_an_explicit_flag(self, tmp_path, settings):
        settings.DECISION_ESCALATION_THRESHOLD = 0.5
        target = tmp_path / "thresholds.json"
        report = _report(tmp_path, self._outcomes())
        call_command(
            "recommend_thresholds",
            str(report),
            "--allow-below-default",
            "--write",
            str(target),
        )
        assert json.loads(target.read_text()) == {"laya": {"team": 0.25}}

    def test_a_threshold_that_missed_on_test_escalates_everything(
        self, tmp_path, capsys
    ):
        target = tmp_path / "thresholds.json"
        report = _report(tmp_path, self._outcomes(test_wrong=6))
        call_command("recommend_thresholds", str(report), "--write", str(target))
        assert "missed the target on test" in capsys.readouterr().out
        assert json.loads(target.read_text()) == {"laya": {"team": 1.0}}

    def test_questions_without_a_qualifying_threshold_escalate_everything(
        self, tmp_path, capsys
    ):
        dev = [Outcome("team", i % 2 == 0, 0.9, split="dev") for i in range(20)]
        target = tmp_path / "thresholds.json"
        call_command(
            "recommend_thresholds", str(_report(tmp_path, dev)), "--write", str(target)
        )
        assert "no threshold met the target on dev" in capsys.readouterr().out
        assert json.loads(target.read_text()) == {"laya": {"team": 1.0}}

    def test_too_few_dev_answers_are_reported_as_insufficient(self, tmp_path, capsys):
        dev = [Outcome("team", True, 0.9, split="dev") for _ in range(5)]
        call_command("recommend_thresholds", str(_report(tmp_path, dev)))
        assert "insufficient dev data" in capsys.readouterr().out

    def test_a_report_without_a_dev_split_is_rejected(self, tmp_path):
        outcomes = [Outcome("team", True, 0.9, split="test")]
        with pytest.raises(CommandError, match="no 'dev' split"):
            call_command("recommend_thresholds", str(_report(tmp_path, outcomes)))


@pytest.mark.unit
def test_compare_lists_skipped_providers_and_uses_the_test_split(tmp_path, capsys):
    outcomes = [Outcome("team", True, 0.9, split="test")]
    outcomes += [Outcome("team", False, 0.9, split="dev")]
    skipped = tmp_path / "jev.json"
    skipped.write_text(
        json.dumps({"status": "skipped", "provider": "jev", "reason": "no key"})
    )
    call_command("compare_decisions", str(_report(tmp_path, outcomes)), str(skipped))
    out = capsys.readouterr().out
    assert "| laya | overall | 1 | n/a | 100.0% |" in out
    assert "| laya | team | 1 | n/a | 100.0% |" in out
    assert "jev: skipped. no key" in out
