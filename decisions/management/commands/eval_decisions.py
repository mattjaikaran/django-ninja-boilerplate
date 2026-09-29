"""Measure one provider's accuracy, calibration, latency, and cost.

Examples::

    python manage.py eval_decisions --benchmark --provider laya --output reports/laya.json
    python manage.py eval_decisions reviewed.jsonl --questions questions.json
    python manage.py eval_decisions --benchmark --split test --json
    python manage.py eval_decisions --benchmark --provider jev --skip-unavailable

This is an operator command, so it may choose a provider. The HTTP and MCP
surfaces always use ``SYSTEMONE_PROVIDER``. The command evaluates exactly the
chosen provider. When that provider is unavailable, it fails; with
``--skip-unavailable`` it records a ``skipped`` report instead. It never runs a
different provider in its place.
"""

import json
import platform
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from api.exceptions import ValidationError
from decisions.providers import PROVIDER_REGISTRY
from decisions.services.eval_dataset import benchmark_domains, load_cases
from decisions.services.eval_service import (
    DecisionEvalService,
    EvalReport,
    skipped_report,
)

#: Labelled dataset used when no path and no --benchmark is given.
DEFAULT_DATASET = (
    Path(__file__).resolve().parents[2] / "data" / "eval" / "support_tickets.json"
)

#: Packages whose versions are recorded in each report.
RECORDED_PACKAGES = ("laya", "torch", "transformers", "typesafe-sdk", "django")


def _pct(value: float | None) -> str:
    return "   n/a" if value is None else f"{value * 100:5.1f}%"


def _ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f} ms"


def environment() -> dict[str, Any]:
    """Return the host and package versions for the report."""
    versions = {}
    for name in RECORDED_PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": versions,
    }


class Command(BaseCommand):
    """Report accuracy, calibration, latency, cost, and threshold coverage."""

    help = "Evaluate one decision provider against labelled cases"

    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        parser.add_argument(
            "datasets",
            nargs="*",
            help="JSON, JSONL, or benchmark domain directory paths",
        )
        parser.add_argument(
            "--benchmark",
            action="store_true",
            help="Evaluate every bundled domain in decisions/data/benchmark",
        )
        parser.add_argument(
            "--questions", help="Question definitions for a JSONL dataset"
        )
        parser.add_argument("--split", help="Keep only cases with this split value")
        parser.add_argument(
            "--provider",
            choices=sorted(PROVIDER_REGISTRY),
            help="Provider to evaluate. Defaults to SYSTEMONE_PROVIDER.",
        )
        parser.add_argument(
            "--skip-unavailable",
            action="store_true",
            help="Record an unavailable provider as skipped instead of failing",
        )
        parser.add_argument(
            "--limit", type=int, help="Evaluate only the first N cases per dataset"
        )
        parser.add_argument("--output", help="Write the JSON report to this path")
        parser.add_argument(
            "--json", action="store_true", help="Print the report as JSON"
        )

    def _paths(self, options: dict[str, Any]) -> list[Path]:
        paths = [Path(p) for p in options["datasets"]]
        if options["benchmark"]:
            paths += benchmark_domains()
        return paths or [DEFAULT_DATASET]

    def handle(self, *args, **options) -> None:
        """Run the evaluation and print or save the report."""
        questions = Path(options["questions"]) if options["questions"] else None
        service = DecisionEvalService(provider=options["provider"])
        try:
            cases = []
            for path in self._paths(options):
                loaded = load_cases(path, questions, options["split"])
                cases += loaded[: options["limit"]] if options["limit"] else loaded
            report: EvalReport | None = service.evaluate(cases, split=options["split"])
            data = report.as_dict()
        except ValidationError as exc:
            raise CommandError(exc.message) from exc
        except ImproperlyConfigured as exc:
            if not options["skip_unavailable"]:
                raise CommandError(str(exc)) from exc
            report = None
            data = skipped_report(service.decisions.provider_name, str(exc))
        data["environment"] = environment()
        if options["output"]:
            Path(options["output"]).parent.mkdir(parents=True, exist_ok=True)
            Path(options["output"]).write_text(json.dumps(data, indent=2) + "\n")
        if options["json"]:
            self.stdout.write(json.dumps(data, indent=2))
        elif report is None:
            self.stdout.write(f"{data['provider']}: skipped. {data['reason']}")
        else:
            self._print(report)

    def _print(self, report: EvalReport) -> None:
        latency = report.latency
        cost = (
            "not configured"
            if report.total_cost is None
            else f"${report.total_cost:.4f}"
        )
        self.stdout.write(
            f"{', '.join(report.datasets)}: {report.cases} cases, provider "
            f"{report.provider}, split {report.split or 'all'}\n"
            f"latency: cold {_ms(latency.cold_ms)}, warm p50 {_ms(latency.p50_ms)}, "
            f"p95 {_ms(latency.p95_ms)} ({latency.warm_count} warm calls); cost {cost}"
        )
        groups = [
            ("overall", report.overall),
            *report.per_dataset.items(),
            *report.per_question.items(),
        ]
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
