"""Recommend per-question escalation thresholds from an eval report.

Examples::

    python manage.py recommend_thresholds reports/laya.json --target 0.9
    python manage.py recommend_thresholds reports/laya.json --write decision_thresholds.json

For each question, the command tunes the lowest threshold on the report's
``dev`` split at which at least ``--min-support`` answers remain and their
accuracy reaches ``--target``. A tuned value below
``DECISION_ESCALATION_THRESHOLD`` is raised to it, unless you pass
``--allow-below-default``. The command then checks the threshold on the
held-out ``test`` split. A threshold is written only when it held there: at
least ``--min-support`` test answers met it, at the target accuracy. Every
other question is written as 1.0, so it always escalates, and the table
shows why.

``--write`` replaces the provider's section in the file that
``DECISION_THRESHOLDS_FILE`` names. It keeps other providers' sections.
"""

from pathlib import Path

from django.conf import settings
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
            help="Fewest accepted answers on dev and on test (default: 10)",
        )
        parser.add_argument(
            "--allow-below-default",
            action="store_true",
            help="Allow thresholds below DECISION_ESCALATION_THRESHOLD",
        )
        parser.add_argument("--write", help="Thresholds file to update")

    def handle(self, *args, **options) -> None:
        """Print the recommendations and optionally write them."""
        if not 0 < options["target"] <= 1:
            raise CommandError("--target must be above 0 and at most 1.")
        floor = (
            0.0
            if options["allow_below_default"]
            else float(settings.DECISION_ESCALATION_THRESHOLD)
        )
        try:
            report = load_report(Path(options["report"]))
            rows = recommend(report, options["target"], options["min_support"], floor)
        except ValidationError as exc:
            raise CommandError(exc.message) from exc
        provider = report["provider"]
        self.stdout.write(
            f"Provider {provider}, target accuracy {_pct(options['target'])}, "
            f"min support {options['min_support']}, floor {floor:.2f}\n"
        )
        self.stdout.write(
            "| Question | Checked | Written | Status | Dev n | Test n | "
            "Test kept | Test accuracy |"
        )
        self.stdout.write("|---|---|---|---|---|---|---|---|")
        for row in rows:
            checked = "none" if row.threshold is None else f"{row.threshold:.2f}"
            self.stdout.write(
                f"| {row.question} | {checked} | {row.written_threshold:.2f} | "
                f"{row.status} | {row.tune_count} | {row.check_count} | "
                f"{row.check_kept} | {_pct(row.check_accuracy)} |"
            )
        if options["write"]:
            path = Path(options["write"])
            write_provider_thresholds(
                path, provider, {row.question: row.written_threshold for row in rows}
            )
            self.stdout.write(f"\nWrote {provider} thresholds to {path}")
