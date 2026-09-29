"""Recommend per-question escalation thresholds from an eval report.

Examples::

    python manage.py recommend_thresholds reports/laya.json --target 0.95
    python manage.py recommend_thresholds reports/laya.json --write decision_thresholds.json

Thresholds are tuned on the report's ``dev`` split: for each question, the
lowest threshold at which at least ``--min-support`` answers remain and their
accuracy reaches ``--target``. The table then shows how each threshold held
on the held-out ``test`` split. A question with no qualifying threshold gets
1.0, so every uncertain answer escalates.

``--write`` replaces the provider's section in the file that
``DECISION_THRESHOLDS_FILE`` names. It keeps other providers' sections.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.exceptions import ValidationError
from decisions.services.eval_compare import load_report, recommend
from decisions.services.thresholds import write_provider_thresholds


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


class Command(BaseCommand):
    """Tune thresholds on dev, check them on test, optionally save them."""

    help = "Recommend per-question escalation thresholds from an eval report"

    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        parser.add_argument("report", help="Report JSON from eval_decisions --output")
        parser.add_argument(
            "--target",
            type=float,
            default=0.95,
            help="Accuracy the accepted answers must reach (default: 0.95)",
        )
        parser.add_argument(
            "--min-support",
            type=int,
            default=10,
            help="Fewest accepted dev answers for a threshold to count (default: 10)",
        )
        parser.add_argument("--write", help="Thresholds file to update")

    def handle(self, *args, **options) -> None:
        """Print the recommendations and optionally write them."""
        if not 0 < options["target"] <= 1:
            raise CommandError("--target must be above 0 and at most 1.")
        try:
            report = load_report(Path(options["report"]))
            rows = recommend(report, options["target"], options["min_support"])
        except ValidationError as exc:
            raise CommandError(exc.message) from exc
        provider = report["provider"]
        self.stdout.write(
            f"Provider {provider}, target accuracy {_pct(options['target'])}, "
            f"min support {options['min_support']}\n"
        )
        self.stdout.write(
            "| Question | Threshold | Dev n | Test n | Test coverage | Test accuracy |"
        )
        self.stdout.write("|---|---|---|---|---|---|")
        for row in rows:
            shown = "none (1.0)" if row.threshold is None else f"{row.threshold:.2f}"
            self.stdout.write(
                f"| {row.question} | {shown} | {row.tune_count} | {row.check_count} | "
                f"{_pct(row.check_coverage)} | {_pct(row.check_accuracy)} |"
            )
        if options["write"]:
            path = Path(options["write"])
            write_provider_thresholds(
                path, provider, {row.question: row.written_threshold for row in rows}
            )
            self.stdout.write(f"\nWrote {provider} thresholds to {path}")
