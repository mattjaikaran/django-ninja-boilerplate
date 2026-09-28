"""Measure a decision provider's accuracy and confidence calibration.

Provider confidence is not trustworthy until you measure it. This service
runs a labelled dataset through a provider and reports, per question and
overall:

* accuracy and mean confidence;
* expected calibration error (ECE) over ten equal-width confidence bins;
* for each candidate escalation threshold, the share of answers at or above
  it (coverage) and their accuracy.

Use the threshold table to pick ``DECISION_ESCALATION_THRESHOLD`` from your
own reviewed data instead of trusting a provider's raw scores.

Dataset format (JSON)::

    {
      "name": "support_tickets",
      "questions": {"team": {"type": "choice", ...}, "angry": {"type": "noul", ...}},
      "cases": [{"state": {...}, "expected": {"team": "billing", "angry": false}}]
    }

``choice`` answers are correct when the label matches. ``noul`` answers are
correct when the yes probability (or boolean) lands on the expected side of
0.5. ``score`` questions are rejected: CLM returns an anchor index, Laya
uses another scale, so one rule would mark a provider wrong for its scale.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from api.exceptions import ValidationError
from decisions.services.decision_service import DecisionService

#: Escalation thresholds reported in the coverage table.
DEFAULT_THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)

#: Number of equal-width bins for the expected calibration error.
CALIBRATION_BINS = 10


@dataclass(frozen=True, slots=True)
class Outcome:
    """One scored answer: was it right, and how confident was the provider."""

    question: str
    correct: bool
    confidence: float


@dataclass(frozen=True, slots=True)
class ThresholdRow:
    """Coverage and accuracy for answers at or above one threshold."""

    threshold: float
    coverage: float
    accuracy: float | None


@dataclass(frozen=True, slots=True)
class Summary:
    """Accuracy and calibration for a group of outcomes."""

    count: int
    accuracy: float
    mean_confidence: float
    ece: float
    thresholds: list[ThresholdRow]


@dataclass(slots=True)
class EvalReport:
    """Result of evaluating a dataset against one provider."""

    dataset: str
    provider: str
    cases: int
    overall: Summary
    per_question: dict[str, Summary] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form of the report."""

        def summary(value: Summary) -> dict[str, Any]:
            return {
                "count": value.count,
                "accuracy": value.accuracy,
                "mean_confidence": value.mean_confidence,
                "ece": value.ece,
                "thresholds": [
                    {
                        "threshold": row.threshold,
                        "coverage": row.coverage,
                        "accuracy": row.accuracy,
                    }
                    for row in value.thresholds
                ],
            }

        return {
            "dataset": self.dataset,
            "provider": self.provider,
            "cases": self.cases,
            "overall": summary(self.overall),
            "per_question": {k: summary(v) for k, v in self.per_question.items()},
        }


def is_correct(question: dict[str, Any], answer: Any, expected: Any) -> bool:
    """Return whether *answer* matches *expected* for *question*'s type."""
    qtype = question.get("type")
    if qtype == "choice":
        return answer == expected
    if qtype == "noul":
        said_yes = answer if isinstance(answer, bool) else float(answer) >= 0.5
        return said_yes is bool(expected)
    if qtype == "score":
        raise ValidationError(
            "Score questions are not supported in eval datasets: providers "
            "report scores on different scales."
        )
    raise ValidationError(f"Unsupported question type '{qtype}' in eval dataset.")


def expected_calibration_error(
    outcomes: Sequence[Outcome], bins: int = CALIBRATION_BINS
) -> float:
    """Weighted mean gap between confidence and accuracy across bins."""
    if not outcomes:
        return 0.0
    total = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        members = [
            o
            for o in outcomes
            if low <= o.confidence < high or (index == bins - 1 and o.confidence == 1)
        ]
        if not members:
            continue
        accuracy = sum(o.correct for o in members) / len(members)
        confidence = sum(o.confidence for o in members) / len(members)
        total += len(members) / len(outcomes) * abs(accuracy - confidence)
    return total


def summarise(
    outcomes: Sequence[Outcome], thresholds: Iterable[float] = DEFAULT_THRESHOLDS
) -> Summary:
    """Summarise *outcomes* into accuracy, calibration, and threshold rows."""
    count = len(outcomes)
    rows = []
    for threshold in thresholds:
        kept = [o for o in outcomes if o.confidence >= threshold]
        rows.append(
            ThresholdRow(
                threshold=threshold,
                coverage=len(kept) / count if count else 0.0,
                accuracy=sum(o.correct for o in kept) / len(kept) if kept else None,
            )
        )
    return Summary(
        count=count,
        accuracy=sum(o.correct for o in outcomes) / count if count else 0.0,
        mean_confidence=(sum(o.confidence for o in outcomes) / count if count else 0.0),
        ece=expected_calibration_error(outcomes),
        thresholds=rows,
    )


class DecisionEvalService:
    """Run a labelled dataset through a decision provider."""

    def __init__(self, provider: str | None = None) -> None:
        """Use *provider*, or ``SYSTEMONE_PROVIDER`` when it is ``None``."""
        self.decisions = DecisionService(provider=provider)

    def evaluate(self, dataset: dict[str, Any]) -> EvalReport:
        """Evaluate every case in *dataset* and return the report.

        Raises:
            ValidationError: If the dataset has no cases or labels an
                unknown question.
        """
        questions: dict[str, Any] = dataset.get("questions") or {}
        cases: list[dict[str, Any]] = dataset.get("cases") or []
        if not cases:
            raise ValidationError("The eval dataset has no cases.")
        outcomes: list[Outcome] = []
        provider_name = self.decisions.provider_name
        for case in cases:
            expected: dict[str, Any] = case["expected"]
            unknown = set(expected) - set(questions)
            if unknown:
                raise ValidationError(
                    f"Expected labels for unknown questions: {sorted(unknown)}."
                )
            asked = {key: questions[key] for key in expected}
            result = self.decisions.decide(case["state"], asked)
            provider_name = result.provider
            for key, label in expected.items():
                outcomes.append(
                    Outcome(
                        question=key,
                        correct=is_correct(asked[key], result.answers[key], label),
                        confidence=result.answer_confidence.get(key, 0.0),
                    )
                )
        return EvalReport(
            dataset=dataset.get("name", "dataset"),
            provider=provider_name,
            cases=len(cases),
            overall=summarise(outcomes),
            per_question={
                key: summarise([o for o in outcomes if o.question == key])
                for key in questions
                if any(o.question == key for o in outcomes)
            },
        )
