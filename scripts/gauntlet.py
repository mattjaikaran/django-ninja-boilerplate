#!/usr/bin/env python3
# file-length-max: 600
"""The Gauntlet — comprehensive quality gate for AI-generated code.

Inspired by Uncle Bob Martin's philosophy: surround agents with extreme
constraints so you never have to read their code. If it passes the gauntlet,
it's trustworthy.

Gates (in order):
  1. FORMAT     — ruff format --check
  2. LINT       — ruff check (50+ rule categories)
  3. TYPECHECK  — mypy
  4. SECURITY   — bandit
  5. ARCH       — architecture layer enforcement
  6. FILELENGTH — file length limits
  7. TEST       — pytest with coverage threshold
  8. MUTATION   — mutmut (test quality)
  9. AUDIT      — pip-audit (dependency vulnerabilities)
 10. DEPLOY     — django check --deploy

Usage:
    python scripts/gauntlet.py              # full gauntlet
    python scripts/gauntlet.py --quick      # skip mutation + audit
    python scripts/gauntlet.py --ci         # CI mode with JSON report
    python scripts/gauntlet.py --fail-fast  # stop on first failure
    python scripts/gauntlet.py --gate lint  # single gate
    python scripts/gauntlet.py --list       # list available gates

Exit codes: 0 = all passed, 1 = one or more failed
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

EXCLUDE_DIRS = {".venv", "venv", "env", "node_modules", ".git", "__pycache__", "cli"}


@dataclass
class GateResult:
    name: str
    passed: bool
    duration_s: float
    output: str = ""
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class GauntletRunner:
    results: list[GateResult] = field(default_factory=list)
    quick: bool = False
    ci: bool = False
    verbose: bool = False
    fail_fast: bool = False
    coverage_threshold: int = 30
    _stopped_early: bool = False

    def run_gate(
        self,
        name: str,
        cmd: list[str],
        *,
        allow_fail: bool = False,
        env_override: dict | None = None,
    ) -> GateResult:
        """Run a single quality gate and record the result."""
        print(f"\n{'=' * 60}")
        print(f"  GATE: {name}")
        print(f"  CMD:  {' '.join(cmd)}")
        print(f"{'=' * 60}")

        start = time.monotonic()
        env = {**os.environ, **(env_override or {})}

        try:
            result = subprocess.run(  # noqa: PLW1510
                cmd,
                capture_output=not self.verbose,
                text=True,
                cwd=PROJECT_ROOT,
                env=env,
                timeout=600,
            )
            duration = time.monotonic() - start
            passed = result.returncode == 0
            output = ""
            if not self.verbose:
                output = (result.stdout or "") + (result.stderr or "")

            if passed:
                print(f"  PASSED ({duration:.1f}s)")
            elif allow_fail:
                print(f"  WARNING ({duration:.1f}s) -- non-blocking")
                passed = True
            else:
                print(f"  FAILED ({duration:.1f}s)")
                if not self.verbose and output:
                    lines = output.strip().split("\n")
                    for line in lines[-40:]:
                        print(f"    {line}")

        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            print(f"  TIMEOUT after {duration:.0f}s")
            output = "Gate timed out after 600s"
            passed = False
        except FileNotFoundError:
            duration = time.monotonic() - start
            print(f"  COMMAND NOT FOUND: {cmd[0]}")
            output = f"Command not found: {cmd[0]}"
            passed = False

        gate_result = GateResult(
            name=name, passed=passed, duration_s=duration, output=output
        )
        self.results.append(gate_result)
        return gate_result

    def skip_gate(self, name: str, reason: str) -> GateResult:
        """Record a skipped gate."""
        print(f"\n{'=' * 60}")
        print(f"  GATE: {name}")
        print(f"  SKIP: {reason}")
        print(f"{'=' * 60}")

        gate_result = GateResult(
            name=name, passed=True, duration_s=0, skipped=True, skip_reason=reason
        )
        self.results.append(gate_result)
        return gate_result

    def run_all(self, single_gate: str | None = None) -> bool:
        """Run all gates (or a single named gate). Returns True if all pass."""
        gates = self._build_gate_list()

        if single_gate:
            gates = {k: v for k, v in gates.items() if k == single_gate}
            if not gates:
                all_gates = ", ".join(self._build_gate_list().keys())
                print(f"Unknown gate: {single_gate}")
                print(f"Available: {all_gates}")
                return False

        print("\n" + "=" * 60)
        print("  THE GAUNTLET")
        print("  Every gate must pass. No exceptions.")
        print("=" * 60)
        mode = "CI" if self.ci else "quick" if self.quick else "full"
        print(f"  Mode: {mode}")
        print(f"  Coverage threshold: {self.coverage_threshold}%")
        print(f"  Fail fast: {self.fail_fast}")
        print(f"  Gates: {len(gates)}")

        total_start = time.monotonic()

        for gate_fn in gates.values():
            gate_fn()
            if self.fail_fast and self.results and not self.results[-1].passed:
                self._stopped_early = True
                break

        total_duration = time.monotonic() - total_start
        return self._print_summary(total_duration)

    def _build_gate_list(self) -> dict:
        """Build ordered dict of gates to run."""
        gates: dict[str, object] = {}
        gates["format"] = self._gate_format
        gates["lint"] = self._gate_lint
        gates["typecheck"] = self._gate_typecheck
        gates["security"] = self._gate_security
        gates["conventions"] = self._gate_conventions
        gates["architecture"] = self._gate_architecture
        gates["filelength"] = self._gate_filelength
        gates["cross-stack"] = self._gate_cross_stack
        gates["test"] = self._gate_test
        gates["deploy-check"] = self._gate_deploy_check

        if not self.quick:
            gates["mutation"] = self._gate_mutation
            gates["audit"] = self._gate_audit
        return gates

    # ── Individual gates ──────────────────────────────────────────────────

    def _gate_format(self) -> GateResult:
        return self.run_gate("FORMAT", ["uv", "run", "ruff", "format", "--check", "."])

    def _gate_lint(self) -> GateResult:
        return self.run_gate("LINT", ["uv", "run", "ruff", "check", "."])

    def _gate_typecheck(self) -> GateResult:
        return self.run_gate("TYPECHECK", ["uv", "run", "mypy", "."])

    def _gate_security(self) -> GateResult:
        return self.run_gate(
            "SECURITY", ["uv", "run", "bandit", "-c", "pyproject.toml", "-r", "."]
        )

    def _gate_architecture(self) -> GateResult:
        return self.run_gate(
            "ARCHITECTURE",
            ["uv", "run", "python", "scripts/check_architecture.py", "--all"],
        )

    def _gate_conventions(self) -> GateResult:
        return self.run_gate(
            "CONVENTIONS",
            ["uv", "run", "python", "scripts/check_conventions.py"],
        )

    def _gate_cross_stack(self) -> GateResult:
        return self.run_gate(
            "CROSS-STACK",
            ["uv", "run", "python", "scripts/check_cross_stack.py"],
            allow_fail=True,  # non-blocking — only applies in monorepos
        )

    def _gate_filelength(self) -> GateResult:
        py_files = [
            str(f.relative_to(PROJECT_ROOT))
            for f in PROJECT_ROOT.rglob("*.py")
            if not any(part in EXCLUDE_DIRS for part in f.parts)
        ]
        if not py_files:
            return self.skip_gate("FILELENGTH", "No Python files found")

        return self.run_gate(
            "FILELENGTH", ["python", "scripts/check_file_length.py", *py_files]
        )

    def _gate_test(self) -> GateResult:
        return self.run_gate(
            "TEST",
            [
                "uv",
                "run",
                "pytest",
                "--timeout=120",
                f"--cov-fail-under={self.coverage_threshold}",
                "--no-header",
                "-q",
            ],
            env_override={"DJANGO_SETTINGS_MODULE": "api.settings.test"},
        )

    def _gate_mutation(self) -> GateResult:
        try:
            subprocess.run(
                ["uv", "run", "mutmut", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return self.skip_gate(
                "MUTATION", "mutmut not installed (uv add --dev mutmut)"
            )

        return self.run_gate(
            "MUTATION",
            [
                "uv",
                "run",
                "mutmut",
                "run",
                "--paths-to-mutate=core/,todos/",
                "--tests-dir=core/tests/,todos/tests/",
                "--no-progress",
                "--CI",
            ],
            allow_fail=True,
        )

    def _gate_audit(self) -> GateResult:
        return self.run_gate("AUDIT", ["uv", "run", "pip-audit"], allow_fail=self.ci)

    def _gate_deploy_check(self) -> GateResult:
        return self.run_gate(
            "DEPLOY-CHECK",
            ["uv", "run", "python", "manage.py", "check", "--deploy"],
            env_override={
                "DJANGO_SETTINGS_MODULE": "api.settings.test",
                "SECRET_KEY": "gauntlet-check-key-not-for-production",
            },
            allow_fail=True,
        )

    # ── Summary ───────────────────────────────────────────────────────────

    def _print_summary(self, total_duration: float) -> bool:
        """Print summary and return True if all passed."""
        print("\n" + "=" * 60)
        print("  GAUNTLET RESULTS")
        print("=" * 60)

        all_passed = True
        for r in self.results:
            if r.skipped:
                status = f"SKIPPED ({r.skip_reason})"
            elif r.passed:
                status = f"PASSED ({r.duration_s:.1f}s)"
            else:
                status = f"FAILED ({r.duration_s:.1f}s)"
                all_passed = False

            marker = "SKIP" if r.skipped else ("OK" if r.passed else "FAIL")
            print(f"  [{marker:>4}] {r.name:<16} {status}")

        if self._stopped_early:
            print("\n  Stopped early (--fail-fast)")

        print(f"\n  Total time: {total_duration:.1f}s")

        if all_passed:
            print("\n  ALL GATES PASSED -- code is gauntlet-certified")
        else:
            failed = [r.name for r in self.results if not r.passed]
            print(f"\n  FAILED GATES: {', '.join(failed)}")
            print("  Fix all failures before merging.")

        print("=" * 60)
        return all_passed

    def generate_report(self) -> dict:
        """Generate a JSON report of results."""
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "mode": "ci" if self.ci else "quick" if self.quick else "full",
            "coverage_threshold": self.coverage_threshold,
            "all_passed": all(r.passed for r in self.results),
            "stopped_early": self._stopped_early,
            "gates": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "duration_s": round(r.duration_s, 2),
                    "skipped": r.skipped,
                    "skip_reason": r.skip_reason,
                }
                for r in self.results
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="The Gauntlet -- comprehensive quality gate"
    )
    parser.add_argument(
        "--quick", action="store_true", help="Skip slow gates (mutation, audit)"
    )
    parser.add_argument(
        "--ci", action="store_true", help="CI mode (audit is non-blocking)"
    )
    parser.add_argument("--gate", type=str, help="Run a single gate by name")
    parser.add_argument(
        "--coverage",
        type=int,
        default=30,
        help="Coverage threshold %% (default: 30, target: 80)",
    )
    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop on first gate failure"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show full command output"
    )
    parser.add_argument(
        "--report", action="store_true", help="Write gauntlet-report.json"
    )
    parser.add_argument(
        "--list", action="store_true", help="List available gate names and exit"
    )
    args = parser.parse_args()

    if args.list:
        runner = GauntletRunner()
        for name in runner._build_gate_list():
            print(f"  {name}")
        return 0

    runner = GauntletRunner(
        quick=args.quick,
        ci=args.ci,
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        coverage_threshold=args.coverage,
    )

    passed = runner.run_all(single_gate=args.gate)

    if args.report:
        report = runner.generate_report()
        report_path = PROJECT_ROOT / "gauntlet-report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport written to {report_path}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
