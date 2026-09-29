"""Compare saved eval reports and recommend per-question thresholds.

Both functions read the JSON reports that ``eval_decisions --output`` writes.
Reports keep every scored answer, so a comparison can be restricted to the
held-out ``test`` split, and thresholds can be tuned on ``dev`` and checked on
``test`` without calling a provider again.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.exceptions import ValidationError
from decisions.services.eval_metrics import (
    Outcome,
    Summary,
    recommend_threshold,
    summarise,
    threshold_row,
)

#: Split used to tune thresholds.
TUNE_SPLIT = "dev"

#: Held-out split used to check them.
CHECK_SPLIT = "test"


def load_report(path: Path) -> dict[str, Any]:
    """Read one report written by ``eval_decisions --output``.

    Raises:
        ValidationError: If the file is unreadable or not a report.
    """
    try:
        report = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Cannot read report {path}: {exc}") from exc
    if not isinstance(report, dict) or "provider" not in report:
        raise ValidationError(f"{path} is not an eval_decisions report.")
    return report


def report_outcomes(report: dict[str, Any], split: str | None) -> list[Outcome]:
    """Return the report's outcomes, limited to *split* when it is set."""
    outcomes = [Outcome.from_dict(o) for o in report.get("outcomes", [])]
    if split:
        outcomes = [o for o in outcomes if o.split == split]
    return outcomes


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    """One provider's result for one question (or ``overall``)."""

    provider: str
    scope: str
    summary: Summary


def compare(
    reports: list[dict[str, Any]], split: str | None, threshold: float
) -> tuple[list[ComparisonRow], list[dict[str, Any]]]:
    """Build comparison rows for every completed report.

    Each row's summary has one threshold row, for *threshold*.

    Returns:
        The rows, and the skipped reports (each with ``provider`` and
        ``reason``) so the caller can show them instead of hiding them.
    """
    rows: list[ComparisonRow] = []
    skipped = []
    for report in reports:
        if report.get("status") == "skipped":
            skipped.append(report)
            continue
        outcomes = report_outcomes(report, split)
        if not outcomes:
            raise ValidationError(
                f"Report for '{report['provider']}' has no outcomes in split '{split}'."
            )
        groups = {"overall": outcomes}
        for key in dict.fromkeys(o.question for o in outcomes):
            groups[key] = [o for o in outcomes if o.question == key]
        rows += [
            ComparisonRow(report["provider"], scope, summarise(group, (threshold,)))
            for scope, group in groups.items()
        ]
    return rows, skipped


#: Recommendation statuses. Only ``held`` writes a tuned threshold; every
#: other status writes 1.0, so the question always escalates.
HELD = "held"
INSUFFICIENT_DEV = "insufficient dev data"
NO_THRESHOLD = "no threshold met the target on dev"
FAILED_TEST = "missed the target on test"


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A tuned threshold for one question and how it held on held-out data.

    Attributes:
        threshold: The threshold checked on ``test``: the value tuned on
            ``dev``, raised to the floor. ``None`` when nothing was tuned.
        status: :data:`HELD` or the reason the question must escalate.
    """

    question: str
    threshold: float | None
    status: str
    tune_count: int
    check_count: int
    check_kept: int
    check_coverage: float | None
    check_accuracy: float | None

    @property
    def written_threshold(self) -> float:
        """Return the value to store: 1.0 unless the threshold held on test."""
        if self.status == HELD and self.threshold is not None:
            return self.threshold
        return 1.0


def recommend(
    report: dict[str, Any],
    target_accuracy: float,
    min_support: int,
    floor: float = 0.0,
) -> list[Recommendation]:
    """Tune a threshold per question on ``dev`` and check it on ``test``.

    A tuned threshold below *floor* is raised to *floor* before the check. A
    threshold holds only when at least *min_support* ``test`` answers meet it
    and their accuracy reaches *target_accuracy*.

    Raises:
        ValidationError: If the report was skipped or has no ``dev`` outcomes.
    """
    if report.get("status") == "skipped":
        raise ValidationError(
            f"Report for '{report['provider']}' was skipped: {report.get('reason')}"
        )
    tune = report_outcomes(report, TUNE_SPLIT)
    if not tune:
        raise ValidationError(
            "The report has no 'dev' split outcomes. Run eval_decisions on a "
            "dataset with dev and test splits, without --split."
        )
    check = report_outcomes(report, CHECK_SPLIT)
    recommendations = []
    for key in dict.fromkeys(o.question for o in tune):
        tuned = [o for o in tune if o.question == key]
        held = [o for o in check if o.question == key]
        threshold = None
        if len(tuned) < min_support:
            status = INSUFFICIENT_DEV
        else:
            tuned_value = recommend_threshold(tuned, target_accuracy, min_support)
            status = NO_THRESHOLD if tuned_value is None else FAILED_TEST
            if tuned_value is not None:
                threshold = max(tuned_value, floor)
        row = threshold_row(held, 1.0 if threshold is None else threshold)
        kept = round(row.coverage * len(held))
        if (
            threshold is not None
            and kept >= min_support
            and row.accuracy is not None
            and row.accuracy >= target_accuracy
        ):
            status = HELD
        recommendations.append(
            Recommendation(
                question=key,
                threshold=threshold,
                status=status,
                tune_count=len(tuned),
                check_count=len(held),
                check_kept=kept,
                check_coverage=row.coverage if held else None,
                check_accuracy=row.accuracy,
            )
        )
    return recommendations
