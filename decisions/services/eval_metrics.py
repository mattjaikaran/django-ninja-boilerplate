"""Accuracy, calibration, latency, and threshold metrics for decision evals.

The functions here are pure: they take scored outcomes and return numbers.
:mod:`decisions.services.eval_service` produces the outcomes, and the
``compare_decisions`` and ``recommend_thresholds`` commands read them back
from saved reports.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

#: Escalation thresholds reported in the coverage table.
DEFAULT_THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)

#: Number of equal-width bins for the expected calibration error.
CALIBRATION_BINS = 10

#: Candidate thresholds searched by :func:`recommend_threshold`.
SEARCH_THRESHOLDS = tuple(round(step / 100, 2) for step in range(0, 100, 5))


@dataclass(frozen=True, slots=True)
class Outcome:
    """One scored answer: was it right, and how confident was the provider."""

    question: str
    correct: bool
    confidence: float
    case_id: str = ""
    split: str = ""
    dataset: str = ""
    answer: Any = None
    expected: Any = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form of the outcome."""
        return {
            "case_id": self.case_id,
            "split": self.split,
            "dataset": self.dataset,
            "question": self.question,
            "answer": self.answer,
            "expected": self.expected,
            "correct": self.correct,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Outcome:
        """Build an outcome from :meth:`as_dict` output."""
        return cls(
            question=data["question"],
            correct=bool(data["correct"]),
            confidence=float(data["confidence"]),
            case_id=data.get("case_id", ""),
            split=data.get("split", ""),
            dataset=data.get("dataset", ""),
            answer=data.get("answer"),
            expected=data.get("expected"),
        )


@dataclass(frozen=True, slots=True)
class ThresholdRow:
    """Coverage and accuracy for answers at or above one threshold."""

    threshold: float
    coverage: float
    accuracy: float | None


@dataclass(frozen=True, slots=True)
class ReliabilityBin:
    """Observed accuracy against mean confidence for one confidence bin."""

    low: float
    high: float
    count: int
    accuracy: float
    mean_confidence: float


@dataclass(frozen=True, slots=True)
class Summary:
    """Accuracy and calibration for a group of outcomes."""

    count: int
    accuracy: float
    mean_confidence: float
    ece: float
    thresholds: list[ThresholdRow]
    bins: list[ReliabilityBin]
    majority_rate: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable form of the summary."""
        return {
            "count": self.count,
            "accuracy": self.accuracy,
            "mean_confidence": self.mean_confidence,
            "ece": self.ece,
            "majority_rate": self.majority_rate,
            "thresholds": [
                {
                    "threshold": r.threshold,
                    "coverage": r.coverage,
                    "accuracy": r.accuracy,
                }
                for r in self.thresholds
            ],
            "reliability": [
                {
                    "low": b.low,
                    "high": b.high,
                    "count": b.count,
                    "accuracy": b.accuracy,
                    "mean_confidence": b.mean_confidence,
                }
                for b in self.bins
            ],
        }


def reliability_bins(
    outcomes: Sequence[Outcome], bins: int = CALIBRATION_BINS
) -> list[ReliabilityBin]:
    """Group *outcomes* into equal-width confidence bins, skipping empty bins.

    A confidence of exactly 1.0 belongs to the last bin.
    """
    rows = []
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        members = [
            o
            for o in outcomes
            if low <= o.confidence < high or (index == bins - 1 and o.confidence >= 1)
        ]
        if not members:
            continue
        rows.append(
            ReliabilityBin(
                low=low,
                high=high,
                count=len(members),
                accuracy=sum(o.correct for o in members) / len(members),
                mean_confidence=sum(o.confidence for o in members) / len(members),
            )
        )
    return rows


def expected_calibration_error(
    outcomes: Sequence[Outcome], bins: int = CALIBRATION_BINS
) -> float:
    """Weighted mean gap between confidence and accuracy across bins."""
    if not outcomes:
        return 0.0
    return sum(
        row.count / len(outcomes) * abs(row.accuracy - row.mean_confidence)
        for row in reliability_bins(outcomes, bins)
    )


def threshold_row(outcomes: Sequence[Outcome], threshold: float) -> ThresholdRow:
    """Return coverage and accuracy for answers at or above *threshold*."""
    kept = [o for o in outcomes if o.confidence >= threshold]
    return ThresholdRow(
        threshold=threshold,
        coverage=len(kept) / len(outcomes) if outcomes else 0.0,
        accuracy=sum(o.correct for o in kept) / len(kept) if kept else None,
    )


def majority_rate(outcomes: Sequence[Outcome]) -> float | None:
    """Return the accuracy of always giving the most common expected label.

    A provider at or below this rate does no better than a constant answer.
    Only meaningful for one question; ``None`` when no label is recorded.
    """
    labels = Counter(repr(o.expected) for o in outcomes if o.expected is not None)
    if not labels:
        return None
    return labels.most_common(1)[0][1] / sum(labels.values())


def summarise(
    outcomes: Sequence[Outcome], thresholds: Iterable[float] = DEFAULT_THRESHOLDS
) -> Summary:
    """Summarise *outcomes* into accuracy, calibration, and threshold rows."""
    count = len(outcomes)
    return Summary(
        count=count,
        accuracy=sum(o.correct for o in outcomes) / count if count else 0.0,
        mean_confidence=sum(o.confidence for o in outcomes) / count if count else 0.0,
        ece=expected_calibration_error(outcomes),
        thresholds=[threshold_row(outcomes, t) for t in thresholds],
        bins=reliability_bins(outcomes),
        majority_rate=majority_rate(outcomes),
    )


def percentile(values: Sequence[float], pct: float) -> float | None:
    """Return the nearest-rank *pct* percentile of *values*, or ``None``."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def recommend_threshold(
    outcomes: Sequence[Outcome],
    target_accuracy: float,
    min_support: int,
    candidates: Iterable[float] = SEARCH_THRESHOLDS,
) -> float | None:
    """Return the lowest threshold whose accepted answers meet the target.

    A candidate qualifies when at least *min_support* answers have that
    confidence or more, and their accuracy is at least *target_accuracy*.
    The lowest qualifying candidate keeps the most answers automatic.

    Returns:
        The threshold, or ``None`` when no candidate qualifies.
    """
    for candidate in sorted(candidates):
        kept = [o for o in outcomes if o.confidence >= candidate]
        if len(kept) < min_support:
            return None
        if sum(o.correct for o in kept) / len(kept) >= target_accuracy:
            return candidate
    return None
