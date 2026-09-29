"""Cheap, typed decisions for coding agents and developer tooling.

Each *pack* is a fixed set of typed questions, loaded from the benchmark
domain that measures it (``data/benchmark/<domain>/questions.json``). One
definition serves both the tool and its eval, so thresholds tuned by
``recommend_thresholds`` apply to exactly the questions the tool asks.

The service answers a pack with the configured provider, applies the
escalation policy, and maps the typed answers to a ``next_step``:

``route_task``
    ``use_local``, ``use_mid``, ``use_frontier``, ``ask_human``, or ``escalate``.
``triage_change``
    ``deep_review``, ``standard_review``, or ``escalate``.
``gate_action``
    ``allow`` or ``ask_human``. The gate fails closed: an uncertain answer asks
    a human, because a wrong ``allow`` costs more than a question.
``pick_generator``
    ``generate`` (with the command to run) or ``escalate``.

``escalate`` means the local answer is too weak: hand the decision to a
stronger model or a person. The service never answers with another provider.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from functools import cache
from typing import Any

from api.exceptions import ValidationError
from decisions.services.decision_service import DecisionService
from decisions.services.eval_dataset import BENCHMARK_DIR
from decisions.services.thresholds import question_thresholds

#: Maps a pack name to the benchmark domain that defines and measures it.
PACK_DOMAINS = {
    "route_task": "task_routing",
    "triage_change": "code_review_triage",
    "gate_action": "risk_flags",
    "pick_generator": "generator_choice",
}

#: Environments ``gate_action`` accepts. Anything but ``local`` asks a human.
ENVIRONMENTS = ("local", "ci", "staging", "production")

#: App names accepted in a suggested generator command.
APP_NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


@cache
def pack_questions(pack: str) -> dict[str, dict[str, Any]]:
    """Return the question definitions for *pack*.

    Raises:
        ValidationError: If *pack* is unknown.
    """
    domain = PACK_DOMAINS.get(pack)
    if domain is None:
        raise ValidationError(
            f"Unknown decision pack '{pack}'. Packs: {', '.join(sorted(PACK_DOMAINS))}."
        )
    data = json.loads((BENCHMARK_DIR / domain / "questions.json").read_text())
    return data["questions"]


@dataclass(frozen=True, slots=True)
class AgentDecision:
    """A pack's typed answers and the step they lead to."""

    pack: str
    provider: str
    next_step: str
    answers: dict[str, Any]
    answer_confidence: dict[str, float]
    escalated_questions: tuple[str, ...]
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved_locally(self) -> bool:
        """Return whether every answer met its escalation threshold."""
        return not self.escalated_questions

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form of the decision."""
        return {
            "pack": self.pack,
            "provider": self.provider,
            "next_step": self.next_step,
            "resolved_locally": self.resolved_locally,
            "answers": self.answers,
            "answer_confidence": self.answer_confidence,
            "escalated_questions": list(self.escalated_questions),
            "details": self.details,
        }


def _yes(value: Any) -> bool:
    """Read a ``noul`` answer: a boolean or a yes probability."""
    return value if isinstance(value, bool) else float(value) >= 0.5


def compact_state(state: dict[str, Any]) -> dict[str, Any]:
    """Drop empty optional fields, so the engine sees only real input."""
    return {k: v for k, v in state.items() if v not in (None, "", [])}


class AgentDecisionService:
    """Answer agent-workflow questions locally and pick the next step."""

    def __init__(self, provider: str | None = None) -> None:
        """Use *provider* for internal callers, else ``SYSTEMONE_PROVIDER``."""
        self.decisions = DecisionService(provider=provider)

    def ask(self, pack: str, state: dict[str, Any]) -> AgentDecision:
        """Answer *pack* for *state* and map the answers to a next step.

        Raises:
            ValidationError: If *pack* is unknown.
            ImproperlyConfigured: If the provider is unavailable.
        """
        result = self.decisions.decide(compact_state(state), pack_questions(pack))
        weak = result.escalated_questions
        step, details = _NEXT_STEP[pack](result.answers, weak)
        return AgentDecision(
            pack=pack,
            provider=result.provider,
            next_step=step,
            answers=result.answers,
            answer_confidence=result.answer_confidence,
            escalated_questions=weak,
            details=details,
        )

    def route_task(self, task: str, files_hint: str = "") -> AgentDecision:
        """Pick the cheapest capable model tier for a coding task."""
        return self.ask("route_task", {"task": task, "files_hint": files_hint})

    def triage_change(
        self,
        title: str,
        description: str = "",
        files: list[str] | None = None,
        additions: int = 0,
        deletions: int = 0,
    ) -> AgentDecision:
        """Classify a PR or commit and choose the review depth."""
        state = {
            "title": title,
            "description": description,
            "files": files or [],
            "additions": additions,
            "deletions": deletions,
        }
        return self.ask("triage_change", state)

    def gate_action(
        self, action: str, environment: str = "local", reason: str = ""
    ) -> AgentDecision:
        """Decide whether an agent may run *action* without approval.

        Two rules do not depend on the model. An *environment* other than
        ``local`` always asks a human. The gate returns ``allow`` only when
        ``DECISION_THRESHOLDS_FILE`` has calibrated thresholds for every gate
        question for the active provider; otherwise it asks a human with the
        reason ``uncalibrated``.

        Raises:
            ValidationError: If *environment* is not a known environment.
        """
        if environment not in ENVIRONMENTS:
            raise ValidationError(
                f"environment must be one of: {', '.join(ENVIRONMENTS)}."
            )
        state = {"action": action, "environment": environment, "reason": reason}
        decision = self.ask("gate_action", state)
        reasons = list(decision.details["reasons"])
        if environment != "local":
            reasons.append(f"environment:{environment}")
        calibrated = question_thresholds(decision.provider)
        if not set(pack_questions("gate_action")) <= set(calibrated):
            reasons.append("uncalibrated")
        step = "ask_human" if reasons else "allow"
        return replace(decision, next_step=step, details={"reasons": reasons})

    def pick_generator(self, request: str, app_name: str = "") -> AgentDecision:
        """Pick the ``generate_feature`` generator for a feature request.

        *app_name* is added to the suggested command only; the engine sees
        the request text alone.

        Raises:
            ValidationError: If *app_name* is not a lowercase identifier.
        """
        if app_name and not APP_NAME.match(app_name):
            raise ValidationError(
                "app_name must be a lowercase identifier of at most 40 characters."
            )
        decision = self.ask("pick_generator", {"request": request})
        if app_name and "command" in decision.details:
            command = f"{decision.details['command']} --app-name {app_name}"
            decision = replace(decision, details={"command": command})
        return decision


StepResult = tuple[str, dict[str, Any]]


def _route(answers: dict[str, Any], weak: tuple[str, ...]) -> StepResult:
    if weak:
        return "escalate", {}
    if _yes(answers["needs_human"]):
        return "ask_human", {}
    return f"use_{answers['tier']}", {}


def _triage(answers: dict[str, Any], weak: tuple[str, ...]) -> StepResult:
    if weak:
        return "escalate", {}
    reasons = [
        name
        for name in ("security_sensitive", "needs_migration_review")
        if _yes(answers[name])
    ]
    return ("deep_review" if reasons else "standard_review"), {"reasons": reasons}


def _gate(answers: dict[str, Any], weak: tuple[str, ...]) -> StepResult:
    reasons = ["uncertain"] if weak else []
    reasons += [n for n in ("destructive", "needs_approval") if _yes(answers[n])]
    if answers["scope"] == "production":
        reasons.append("production")
    return ("ask_human" if reasons else "allow"), {"reasons": reasons}


def _generator(answers: dict[str, Any], weak: tuple[str, ...]) -> StepResult:
    if weak:
        return "escalate", {}
    command = f"uv run python manage.py generate_feature {answers['generator']}"
    return "generate", {"command": command}


_NEXT_STEP = {
    "route_task": _route,
    "triage_change": _triage,
    "gate_action": _gate,
    "pick_generator": _generator,
}
