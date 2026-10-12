#!/usr/bin/env python3
"""JOURNEYS gate: features, user journeys, and Playwright evidence agree.

Reads ``docs/product/FEATURES.md``, ``docs/product/journeys/*.md``, the
frontend Playwright sources, and the Playwright JSON report, then applies
the sync rules in ``docs/product/README.md``. Runs without Django.

Paths come from ``JOURNEYS_SPEC_DIR``, ``JOURNEYS_E2E_DIR``,
``JOURNEYS_E2E_REPORT`` and ``TICKETS_DIR`` (defaults in the README).

Usage:
    python scripts/check_journeys.py           # errors, warnings, gaps
    python scripts/check_journeys.py --json    # full report as JSON

Exit: 0 = no errors (warnings and gaps allowed), 1 = at least one error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journeys.services.spec_service import (
    Issue,
    SyncReport,
    build_report,
    spec_paths,
)


def _line(issue: Issue) -> str:
    where = f" ({issue.path})" if issue.path else ""
    return f"  {issue.code}: {issue.message}{where}"


def _print_text(report: SyncReport) -> None:
    paths = report.paths
    e2e = "found" if report.e2e_dir_exists else "missing"
    results = "found" if report.report_exists else "missing"
    print(f"JOURNEYS: spec {paths.spec_dir}")
    print(f"  e2e dir {paths.e2e_dir} ({e2e})")
    print(f"  report  {paths.e2e_report} ({results})")
    print(
        f"  {len(report.features)} features, {len(report.journeys)} journeys, "
        f"{report.verified_journeys} verified"
    )
    for label, issues in (
        ("errors", report.errors),
        ("warnings", report.warnings),
        ("gaps", report.gaps),
    ):
        if issues:
            print(f"{label} ({len(issues)}):")
            for issue in issues:
                print(_line(issue))
    if report.errors:
        print(
            f"JOURNEYS: FAIL ({len(report.errors)} errors). See docs/product/README.md."
        )
    else:
        print(
            f"JOURNEYS: OK ({len(report.warnings)} warnings, {len(report.gaps)} gaps)"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="JOURNEYS gate: spec, journeys, e2e agree."
    )
    parser.add_argument(
        "--json", action="store_true", help="print the full report as JSON"
    )
    args = parser.parse_args(argv)
    report = build_report(spec_paths(ROOT))
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        _print_text(report)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
