"""Measure provider accuracy and confidence calibration on a labelled set.

Examples::

    python manage.py eval_decisions                       # bundled tickets, configured provider
    python manage.py eval_decisions --provider laya
    python manage.py eval_decisions path/to/reviewed.json --json

This is an operator command, so it may choose a provider. The HTTP and MCP
surfaces always use ``SYSTEMONE_PROVIDER``.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from decisions.providers import PROVIDER_REGISTRY
from decisions.services import DecisionEvalService

#: Labelled dataset shipped with the app.
DEFAULT_DATASET = (
    Path(__file__).resolve().parents[2] / "data" / "eval" / "support_tickets.json"
)


def _pct(value: float | None) -> str:
    return "   n/a" if value is None else f"{value * 100:5.1f}%"


class Command(BaseCommand):
    """Report accuracy, calibration error, and threshold coverage."""

    help = "Evaluate a decision provider against a labelled dataset"

    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        parser.add_argument("dataset", nargs="?", default=str(DEFAULT_DATASET))
        parser.add_argument(
            "--provider",
            choices=sorted(PROVIDER_REGISTRY),
            help="Provider to evaluate. Defaults to SYSTEMONE_PROVIDER.",
        )
        parser.add_argument(
            "--json", action="store_true", help="Print the report as JSON"
        )

    def handle(self, *args, **options) -> None:
        """Run the evaluation and print the report."""
        path = Path(options["dataset"])
        if not path.is_file():
            raise CommandError(f"Dataset not found: {path}")
        dataset = json.loads(path.read_text())
        report = DecisionEvalService(provider=options["provider"]).evaluate(dataset)
        if options["json"]:
            self.stdout.write(json.dumps(report.as_dict(), indent=2))
            return

        self.stdout.write(
            f"{report.dataset}: {report.cases} cases, provider {report.provider}"
        )
        groups = [("overall", report.overall), *report.per_question.items()]
        for name, summary in groups:
            self.stdout.write(
                f"\n{name}: accuracy {_pct(summary.accuracy)}, "
                f"mean confidence {_pct(summary.mean_confidence)}, "
                f"ECE {summary.ece:.3f} ({summary.count} answers)"
            )
            for row in summary.thresholds:
                self.stdout.write(
                    f"  confidence >= {row.threshold:.2f}: "
                    f"coverage {_pct(row.coverage)}, accuracy {_pct(row.accuracy)}"
                )
