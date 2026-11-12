"""Output helpers for scripts/gauntlet.py: quiet gate lines, logs and reports.

Default runs print one line per gate, the last lines of a failing gate and the
path of its full log under `.gauntlet/last/`. `--verbose` streams every gate.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from gauntlet_gates import GateResult
from gauntlet_hints import FIX_HINTS

TAIL_LINES = 40
# The TEST gate keeps its pytest count line visible when it passes.
RAW_SUMMARY_GATES = frozenset({"TEST"})


def tail(output: str, lines: int = TAIL_LINES) -> list[str]:
    """Return the last `lines` non-empty lines of a gate's output."""
    stripped = output.strip()
    return stripped.split("\n")[-lines:] if stripped else []


def count_line(output: str) -> str:
    """Return the last non-empty line of a gate's output, or an empty string."""
    lines = tail(output, lines=1)
    return lines[0] if lines else ""


def print_header(name: str, cmd: list[str], verbose: bool) -> None:
    """Print the gate banner in verbose mode, or a single line otherwise."""
    if not verbose:
        print(f"  RUN    {name}")
        return
    print(f"\n{'=' * 60}")
    print(f"  GATE: {name}")
    print(f"  CMD:  {' '.join(cmd)}")
    print(f"{'=' * 60}")


def write_log(root: Path, name: str, cmd: list[str], output: str) -> Path:
    """Write one gate's full output under `.gauntlet/last/` and return its path."""
    directory = root / ".gauntlet" / "last"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name.lower()}.log"
    path.write_text(f"$ {' '.join(cmd)}\n{output}", encoding="utf-8")
    return path


def build_report(results: list[GateResult], mode: str, stopped_early: bool) -> dict:
    """Build the JSON report for one run."""
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mode": mode,
        "all_passed": all(r.passed for r in results),
        "blocking_passed": all(r.passed or r.warning for r in results),
        "has_warnings": any(r.warning for r in results),
        "stopped_early": stopped_early,
        "gates": [
            {
                "name": r.name,
                "passed": r.passed,
                "duration_s": round(r.duration_s, 2),
                "warning": r.warning,
                "skipped": r.skipped,
                "skip_reason": r.skip_reason,
                "fix_hint": "" if r.passed else FIX_HINTS.get(r.name, ""),
                "log": r.log,
            }
            for r in results
        ],
    }


def write_report(root: Path, report: dict) -> Path:
    """Write the latest run's report to `.gauntlet/last/report.json`."""
    directory = root / ".gauntlet" / "last"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
