"""Tests for agent decisions: next steps, git input, and the API surface."""

import json
import subprocess

import pytest
from django.core.management import call_command

from api.exceptions import ValidationError
from core.tests.factories import UserFactory
from decisions.providers.base import DecisionProvider, DecisionResult
from decisions.services import DecisionService
from decisions.services.agent_service import AgentDecisionService, pack_questions
from decisions.services.git_changes import commit_state, commits_in_range


class _Scripted(DecisionProvider):
    """Answer every question from a fixed table."""

    name = "scripted"

    def __init__(self, answers, confidence=0.9):
        self.answers = answers
        self.confidence = confidence
        self.seen_states: list[dict] = []

    def is_available(self) -> bool:
        return True

    def predict(self, state, questions) -> DecisionResult:
        self.seen_states.append(state)
        conf = self.confidence
        confidences = {
            k: conf[k] if isinstance(conf, dict) else conf for k in questions
        }
        return DecisionResult(
            answers={k: self.answers[k] for k in questions},
            answer_confidence=confidences,
            confidence=min(confidences.values()),
            provider=self.name,
        )


@pytest.fixture(autouse=True)
def clean(settings):
    settings.DECISION_THRESHOLDS_FILE = ""
    settings.DECISION_ESCALATION_THRESHOLD = 0.5
    DecisionService._providers.clear()
    yield
    DecisionService._providers.clear()


def _use(answers, confidence=0.9):
    provider = _Scripted(answers, confidence)
    DecisionService._providers["fake"] = provider
    return provider


def _service():
    return AgentDecisionService(provider="fake")


def _calibrate(settings, tmp_path, provider="scripted"):
    """Write thresholds for every gate question, as a calibrated setup would."""
    path = tmp_path / "thresholds.json"
    gate = dict.fromkeys(pack_questions("gate_action"), 0.5)
    path.write_text(json.dumps({provider: gate}))
    settings.DECISION_THRESHOLDS_FILE = str(path)


@pytest.mark.unit
class TestNextStep:
    @pytest.mark.parametrize(
        ("tier", "needs_human", "step"),
        [
            ("local", False, "use_local"),
            ("frontier", False, "use_frontier"),
            ("mid", True, "ask_human"),
        ],
    )
    def test_route_task(self, tier, needs_human, step):
        _use({"tier": tier, "needs_human": needs_human})
        assert _service().route_task("Rename a function").next_step == step

    def test_a_weak_answer_escalates_the_route(self):
        _use({"tier": "local", "needs_human": False}, {"tier": 0.3, "needs_human": 0.9})
        decision = _service().route_task("Fix the flaky test")
        assert (decision.next_step, decision.escalated_questions) == (
            "escalate",
            ("tier",),
        )
        assert decision.resolved_locally is False

    def test_triage_lists_the_reasons_for_a_deep_review(self):
        _use(
            {
                "change_type": "feature",
                "needs_migration_review": True,
                "security_sensitive": 0.2,
            }
        )
        decision = _service().triage_change("Add invoice due date")
        assert decision.next_step == "deep_review"
        assert decision.details == {"reasons": ["needs_migration_review"]}

    def test_gate_allows_only_a_calibrated_confident_safe_local_action(
        self, settings, tmp_path
    ):
        _calibrate(settings, tmp_path)
        _use({"destructive": False, "needs_approval": False, "scope": "local"})
        assert _service().gate_action("uv run pytest").next_step == "allow"

    @pytest.mark.parametrize(
        ("answers", "confidence", "reasons"),
        [
            (
                {"destructive": True, "needs_approval": False, "scope": "local"},
                0.9,
                ["destructive"],
            ),
            (
                {"destructive": False, "needs_approval": False, "scope": "production"},
                0.9,
                ["production"],
            ),
            (
                {"destructive": False, "needs_approval": False, "scope": "local"},
                0.2,
                ["uncertain"],
            ),
        ],
    )
    def test_gate_fails_closed(self, answers, confidence, reasons, settings, tmp_path):
        _calibrate(settings, tmp_path)
        _use(answers, confidence)
        decision = _service().gate_action("something")
        assert (decision.next_step, decision.details["reasons"]) == (
            "ask_human",
            reasons,
        )

    def test_a_non_local_environment_always_asks_a_human(self, settings, tmp_path):
        _calibrate(settings, tmp_path)
        _use({"destructive": False, "needs_approval": False, "scope": "local"})
        decision = _service().gate_action("drop table users", "production")
        assert (decision.next_step, decision.details["reasons"]) == (
            "ask_human",
            ["environment:production"],
        )

    def test_the_global_default_alone_never_allows(self):
        _use({"destructive": False, "needs_approval": False, "scope": "local"})
        decision = _service().gate_action("uv run pytest")
        assert (decision.next_step, decision.details["reasons"]) == (
            "ask_human",
            ["uncalibrated"],
        )

    @pytest.mark.parametrize("environment", ["prod", "Production", ""])
    def test_unknown_environments_are_rejected(self, environment):
        _use({"destructive": False, "needs_approval": False, "scope": "local"})
        with pytest.raises(ValidationError, match="environment must be one of"):
            _service().gate_action("ls", environment)

    def test_generator_command_keeps_app_name_out_of_the_engine_state(self):
        provider = _use({"generator": "file_storage"})
        decision = _service().pick_generator("Let users upload avatars", "avatars")
        assert decision.details == {
            "command": "uv run python manage.py generate_feature file_storage "
            "--app-name avatars"
        }
        assert provider.seen_states == [{"request": "Let users upload avatars"}]

    def test_generator_rejects_an_unsafe_app_name(self):
        _use({"generator": "chat"})
        with pytest.raises(ValidationError, match="app_name"):
            _service().pick_generator("chat", "x; rm -rf /")

    def test_unknown_pack_is_rejected(self):
        with pytest.raises(ValidationError, match="Unknown decision pack"):
            pack_questions("deploy")

    def test_per_question_threshold_file_drives_escalation(self, settings, tmp_path):
        path = tmp_path / "t.json"
        path.write_text(json.dumps({"scripted": {"tier": 0.95}}))
        settings.DECISION_THRESHOLDS_FILE = str(path)
        _use({"tier": "local", "needs_human": False}, 0.9)
        assert _service().route_task("Rename").next_step == "escalate"


@pytest.fixture
def repo(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "dev@example.com")
    git("config", "user.name", "Dev")
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n")
    git("add", ".")
    git("commit", "-q", "-m", "feat(core): Add a\n\nBody line.")
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.bin").write_bytes(b"\0\1")
    git("add", ".")
    git("commit", "-q", "-m", "fix(core): Drop y")
    return tmp_path


@pytest.mark.unit
class TestGitChanges:
    def test_commit_state_reads_message_files_and_counts(self, repo):
        assert commit_state("HEAD~1", repo) == {
            "title": "feat(core): Add a",
            "description": "Body line.",
            "files": ["a.py"],
            "additions": 2,
            "deletions": 0,
        }
        head = commit_state("HEAD", repo)
        assert (head["files"], head["deletions"]) == (["a.py", "b.bin"], 1)

    def test_range_is_oldest_first_and_limited(self, repo):
        assert len(commits_in_range("HEAD", repo, 0)) == 2
        assert (
            commits_in_range("HEAD", repo, 1) == commits_in_range("HEAD", repo, 0)[1:]
        )

    def test_option_like_revisions_are_rejected(self, repo):
        with pytest.raises(ValidationError, match="Invalid git revision"):
            commit_state("--output=/tmp/x", repo)


@pytest.mark.unit
class TestAgentDecideCommand:
    def test_allow_prints_json_and_exits_zero(self, capsys, settings, tmp_path):
        settings.SYSTEMONE_PROVIDER = "fake"
        _calibrate(settings, tmp_path, "fake")
        call_command("agent_decide", "gate", "uv run pytest")
        assert json.loads(capsys.readouterr().out)["next_step"] == "allow"

    def test_an_uncalibrated_gate_exits_with_status_3(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        with pytest.raises(SystemExit) as exit_info:
            call_command("agent_decide", "gate", "uv run pytest")
        assert exit_info.value.code == 3

    def test_a_handover_exits_with_status_3(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        settings.DECISION_ESCALATION_THRESHOLD = 0.999
        with pytest.raises(SystemExit) as exit_info:
            call_command("agent_decide", "route", "Rename a helper")
        assert exit_info.value.code == 3


@pytest.fixture
def auth_client(api_client):
    from ninja_jwt.tokens import RefreshToken

    token = RefreshToken.for_user(UserFactory()).access_token
    api_client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return api_client


def _post(client, path, payload):
    return client.post(
        f"/api/decisions/agent/{path}",
        data=json.dumps(payload),
        content_type="application/json",
    )


@pytest.mark.django_db
class TestAgentEndpoints:
    def test_route_task_returns_the_decision(self, auth_client, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        response = _post(auth_client, "route-task", {"task": "Rename a helper"})
        assert response.status_code == 200
        body = response.json()
        assert (body["pack"], body["provider"], body["resolvedLocally"]) == (
            "route_task",
            "fake",
            True,
        )

    @pytest.mark.parametrize("field", ["provider", "thresholds"])
    def test_callers_cannot_choose_provider_or_threshold(self, auth_client, field):
        response = _post(auth_client, "gate-action", {"action": "ls", field: "fake"})
        assert response.status_code == 422

    def test_anonymous_callers_are_rejected(self, api_client):
        assert _post(api_client, "route-task", {"task": "x"}).status_code == 401

    def test_unavailable_provider_is_a_500_with_the_hint(self, auth_client, settings):
        settings.SYSTEMONE_PROVIDER = "jev"
        settings.TYPESAFE_API_KEY = ""
        response = _post(auth_client, "pick-generator", {"request": "Add chat"})
        assert response.status_code == 500
        assert response.json()["error"] == "provider_unavailable"
