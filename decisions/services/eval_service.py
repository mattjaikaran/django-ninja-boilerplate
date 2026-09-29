"""Measure a decision provider's accuracy, calibration, latency, and cost.

Provider confidence is not trustworthy until you measure it. This service
runs labelled cases through one provider and reports, overall, per dataset,
and per question:

* accuracy and mean confidence;
* expected calibration error (ECE) and reliability bins over ten
  equal-width confidence bins;
* for each candidate escalation threshold, the share of answers at or above
  it (coverage) and their accuracy.

It also records latency per request (cold first call apart from warm p50 and
p95) and, when ``DECISION_PROVIDER_COSTS`` sets a price, the cost per call.
Every scored answer is kept in the report, so ``recommend_thresholds`` can
tune on the ``dev`` split and check on the held-out ``test`` split later.

The service evaluates exactly the provider it is given. If that provider is
unavailable it raises; it never substitutes another provider.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from api.exceptions import ValidationError
from decisions.services.decision_service import DecisionService
from decisions.services.eval_dataset import EvalCase, check_question_keys, is_correct
from decisions.services.eval_metrics import Outcome, Summary, percentile, summarise

#: Report format version, bumped when the JSON shape changes.
REPORT_VERSION = 2


@dataclass(frozen=True, slots=True)
class Latency:
    """Request latency in milliseconds."""

    cold_ms: float | None
    p50_ms: float | None
    p95_ms: float | None
    warm_count: int

    @classmethod
    def from_samples(cls, samples: Sequence[float]) -> Latency:
        """Treat the first sample as cold and the rest as warm."""
        warm = list(samples[1:])
        return cls(
            cold_ms=samples[0] if samples else None,
            p50_ms=percentile(warm, 50),
            p95_ms=percentile(warm, 95),
            warm_count=len(warm),
        )


@dataclass(slots=True)
class EvalReport:
    """Result of evaluating labelled cases against one provider."""

    provider: str
    datasets: list[str]
    cases: int
    overall: Summary
    latency: Latency
    cost_per_call: float | None
    per_dataset: dict[str, Summary] = field(default_factory=dict)
    per_question: dict[str, Summary] = field(default_factory=dict)
    outcomes: list[Outcome] = field(default_factory=list)
    split: str | None = None

    @property
    def total_cost(self) -> float | None:
        """Return the cost of every call, or ``None`` without a price."""
        if self.cost_per_call is None:
            return None
        return self.cost_per_call * self.cases

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form of the report."""
        return {
            "version": REPORT_VERSION,
            "status": "ok",
            "provider": self.provider,
            "datasets": self.datasets,
            "split": self.split,
            "cases": self.cases,
            "latency": {
                "cold_ms": self.latency.cold_ms,
                "p50_ms": self.latency.p50_ms,
                "p95_ms": self.latency.p95_ms,
                "warm_count": self.latency.warm_count,
            },
            "cost_per_call": self.cost_per_call,
            "total_cost": self.total_cost,
            "overall": self.overall.as_dict(),
            "per_dataset": {k: v.as_dict() for k, v in self.per_dataset.items()},
            "per_question": {k: v.as_dict() for k, v in self.per_question.items()},
            "outcomes": [o.as_dict() for o in self.outcomes],
        }


def skipped_report(provider: str, reason: str) -> dict[str, Any]:
    """Return the report for a provider the operator chose to skip."""
    return {
        "version": REPORT_VERSION,
        "status": "skipped",
        "provider": provider,
        "reason": reason,
    }


def provider_cost(provider: str) -> float | None:
    """Return the configured price per call for *provider*, if any."""
    costs = getattr(settings, "DECISION_PROVIDER_COSTS", {}) or {}
    value = costs.get(provider)
    return None if value is None else float(value)


def _grouped(outcomes: list[Outcome], attr: str) -> dict[str, Summary]:
    keys = dict.fromkeys(getattr(o, attr) for o in outcomes)
    return {
        key: summarise([o for o in outcomes if getattr(o, attr) == key]) for key in keys
    }


class DecisionEvalService:
    """Run labelled cases through one decision provider."""

    def __init__(self, provider: str | None = None) -> None:
        """Use *provider*, or ``SYSTEMONE_PROVIDER`` when it is ``None``."""
        self.decisions = DecisionService(provider=provider)

    def require_available(self) -> None:
        """Fail before any case runs when the provider cannot serve requests.

        Raises:
            ImproperlyConfigured: If the provider reports it is unavailable.
        """
        name = self.decisions.provider_name
        if not self.decisions.get_provider().is_available():
            raise ImproperlyConfigured(
                f"Decision provider '{name}' is not available. Configure it, "
                "or pass --skip-unavailable to record it as skipped."
            )

    def evaluate(self, cases: list[EvalCase], split: str | None = None) -> EvalReport:
        """Evaluate every case and return the report.

        Args:
            cases: Validated cases from :func:`load_cases`.
            split: Split label to record in the report.

        Raises:
            ValidationError: If there are no cases or a question key has two
                definitions.
            ImproperlyConfigured: If the provider is unavailable.
        """
        if not cases:
            raise ValidationError("The eval dataset has no cases.")
        check_question_keys(cases)
        self.require_available()
        outcomes: list[Outcome] = []
        samples: list[float] = []
        provider_name = self.decisions.provider_name
        for case in cases:
            started = time.perf_counter()
            result = self.decisions.decide(case.state, case.questions)
            samples.append((time.perf_counter() - started) * 1000)
            provider_name = result.provider
            for key, label in case.expected.items():
                answer = result.answers[key]
                outcomes.append(
                    Outcome(
                        question=key,
                        correct=is_correct(case.questions[key], answer, label),
                        confidence=result.answer_confidence.get(key, 0.0),
                        case_id=case.case_id,
                        split=case.split,
                        dataset=case.dataset,
                        answer=answer,
                        expected=label,
                    )
                )
        return EvalReport(
            provider=provider_name,
            datasets=list(dict.fromkeys(case.dataset for case in cases)),
            cases=len(cases),
            overall=summarise(outcomes),
            latency=Latency.from_samples(samples),
            cost_per_call=provider_cost(provider_name),
            per_dataset=_grouped(outcomes, "dataset"),
            per_question=_grouped(outcomes, "question"),
            outcomes=outcomes,
            split=split,
        )
