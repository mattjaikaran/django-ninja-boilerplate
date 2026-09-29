"""Compare saved eval reports side by side as Markdown tables.

Examples::

    python manage.py compare_decisions reports/laya.json reports/clm.json
    python manage.py compare_decisions reports/*.json --split all

By default the tables use only the held-out ``test`` split. Skipped
providers are listed with their reason, not left out.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.exceptions import ValidationError
from decisions.services.eval_compare import CHECK_SPLIT, compare, load_report


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f}"


def _cost(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.5f}"


class Command(BaseCommand):
    """Print accuracy, calibration, coverage, latency, and cost per provider."""

    help = "Compare eval_decisions JSON reports"

    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        parser.add_argument("reports", nargs="+", help="Report JSON paths")
        parser.add_argument(
            "--split",
            default=CHECK_SPLIT,
            help="Split to compare, or 'all' for every case (default: test)",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=0.8,
            help="Threshold for the coverage columns (default: 0.8)",
        )

    def handle(self, *args, **options) -> None:
        """Print the comparison."""
        split = None if options["split"] == "all" else options["split"]
        at = options["threshold"]
        try:
            reports = [load_report(Path(path)) for path in options["reports"]]
            rows, skipped = compare(reports, split, at)
        except ValidationError as exc:
            raise CommandError(exc.message) from exc
        self.stdout.write(f"Split: {options['split']}\n")
        self.stdout.write(
            "| Provider | Question | n | Majority | Accuracy | Mean conf. | ECE | "
            f"Coverage at {at:.2f} | Accuracy at {at:.2f} |"
        )
        self.stdout.write("|---|---|---|---|---|---|---|---|---|")
        for row in rows:
            s, cut = row.summary, row.summary.thresholds[0]
            # A majority rate is only meaningful for one question.
            majority = None if row.scope == "overall" else s.majority_rate
            self.stdout.write(
                f"| {row.provider} | {row.scope} | {s.count} | {_pct(majority)} | "
                f"{_pct(s.accuracy)} | {_pct(s.mean_confidence)} | {s.ece:.3f} | "
                f"{_pct(cut.coverage)} | {_pct(cut.accuracy)} |"
            )
        self.stdout.write(
            "\n| Provider | Cases (all splits) | Cold ms | p50 ms | p95 ms | "
            "Cost per call | Total cost |"
        )
        self.stdout.write("|---|---|---|---|---|---|---|")
        for report in reports:
            if report.get("status") == "skipped":
                continue
            latency = report["latency"]
            self.stdout.write(
                f"| {report['provider']} | {report['cases']} | "
                f"{_ms(latency['cold_ms'])} | {_ms(latency['p50_ms'])} | "
                f"{_ms(latency['p95_ms'])} | {_cost(report['cost_per_call'])} | "
                f"{_cost(report['total_cost'])} |"
            )
        for report in skipped:
            self.stdout.write(f"\n{report['provider']}: skipped. {report['reason']}")
