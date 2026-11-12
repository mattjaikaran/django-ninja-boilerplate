#!/usr/bin/env python3
"""Report whether upgrading this project to a target Django release is safe.

Usage:
    uv run --extra dev ... python scripts/django_upgrade_check.py <6.0|6.1>
    [--json] [--run-tests]

Checks, in order:

1. Install blockers. Resolve the project with Django pinned to the target.
   Then resolve each dependency alone with Django pinned, so every conflict
   is listed, not only the first one uv reports.
2. Declared support. Locked Django packages that publish per-release Django
   classifiers (for example "Framework :: Django :: 5.2") but do not list the
   target (warning). Packages that never publish them are skipped.
3. First-party code. Deprecations of the target release that fire while the
   test suite runs on the current Django (blocker), and django-upgrade
   fixers that the target adds, measured after the prior release's fixers
   are applied (warning).
4. Tests (--run-tests only). The suite on the target Django.

Verdicts: BLOCKED (exit 1), SAFE WITH WARNINGS (exit 2), SAFE (exit 0).
Usage errors exit 3. A check that cannot run (PyPI, uv) is a warning, not a
pass. Step 3 only sees code that the suite executes.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
import xml.etree.ElementTree as ET  # nosec B405: parses only the JUnit file this script asks pytest to write
from pathlib import Path
from typing import Any, NamedTuple

REPO = Path(__file__).resolve().parent.parent
SUPPORTED_TARGETS = ("6.0", "6.1")
# Deprecation warnings that announce removal in each target release. Upgrading
# to 6.1 from 5.2 crosses both removals, so both are scanned.
REMOVAL_WARNINGS = {
    "6.0": ("RemovedInDjango60Warning",),
    "6.1": ("RemovedInDjango60Warning", "RemovedInDjango61Warning"),
}
DJANGO_UPGRADE = "django-upgrade==1.33.0"
PYPI = "https://pypi.org/pypi"
NEWEST_RELEASES = 25  # releases examined when looking for an alternative
PARALLEL = 8
PY_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
EXIT_CODES = {"BLOCKED": 1, "SAFE WITH WARNINGS": 2, "SAFE": 0}
SKIP_DIRS = {"node_modules", "__pycache__", "site-packages"}
REQ_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
DJANGO_REQ = re.compile(r"django(?![\w.-])", re.IGNORECASE)
RELEASE = re.compile(r"\d+(\.\d+)*")
REMOVED_IN = re.compile(r"RemovedInDjango(\d)(\d)Warning")
DEPENDS_ON = re.compile(r"Because (\S+) depends on (django\S*)")
BASELINE = {"6.0": "5.2", "6.1": "6.0"}
VERSIONED_CLASSIFIER = re.compile(r"Framework :: Django :: \d")

# Pytest plugin that records every warning. Loaded from a temp directory so
# nothing is added to the repository.
PROBE_PLUGIN = '''\
"""Record pytest warnings for django-upgrade-check."""

import json
import os

_records = []


def pytest_warning_recorded(warning_message, when, nodeid):
    _records.append(
        {
            "category": warning_message.category.__name__,
            "filename": str(warning_message.filename),
            "lineno": warning_message.lineno,
            "message": str(warning_message.message),
        }
    )


def pytest_sessionfinish(session, exitstatus):
    with open(os.environ["DJANGO_UPGRADE_PROBE_OUT"], "w", encoding="utf-8") as out:
        json.dump(_records, out)
'''


class PyPIError(Exception):
    """A PyPI metadata request failed."""


class Requirement(NamedTuple):
    text: str
    origin: str  # "base" or "extra:<name>"


class Resolution(NamedTuple):
    status: str  # "ok", "conflict", or "error"
    message: str


@dataclasses.dataclass(frozen=True)
class Finding:
    severity: str  # "blocker" or "warning"
    source: str
    subject: str
    detail: str
    alternative: str


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def req_name(text: str) -> str:
    match = REQ_NAME.match(text)
    if match is None:
        raise ValueError(f"Cannot read a package name from {text!r}")
    return normalize(match.group(0))


def release_of(version: str) -> tuple[int, int]:
    major, minor = (int(part) for part in version.split(".")[:2])
    return major, minor


def load_requirements() -> list[Requirement]:
    """Return base and extra dependencies, without Django or the project."""
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    own = normalize(project["name"])
    found = [Requirement(text, "base") for text in project["dependencies"]]
    for extra, texts in project.get("optional-dependencies", {}).items():
        found += [Requirement(text, f"extra:{extra}") for text in texts]
    return [req for req in found if req_name(req.text) not in {"django", own}]


def compile_requirements(lines: list[str]) -> Resolution:
    """Resolve requirement lines with uv, without touching the project env."""
    with tempfile.TemporaryDirectory() as tmp:
        infile = Path(tmp) / "requirements.in"
        infile.write_text("\n".join(lines) + "\n", encoding="utf-8")
        proc = subprocess.run(
            [
                "uv",
                "pip",
                "compile",
                str(infile),
                "-o",
                str(Path(tmp) / "pins.txt"),
                "-q",
                "--python-version",
                PY_VERSION,
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
    if proc.returncode == 0:
        return Resolution("ok", "")
    if "No solution found" in proc.stderr:
        return Resolution("conflict", conflict_detail(proc.stderr))
    first = next((ln.strip() for ln in proc.stderr.splitlines() if ln.strip()), "")
    return Resolution("error", first or f"uv exited {proc.returncode}")


def conflict_detail(stderr: str) -> str:
    """Summarize a uv conflict as "<package> requires django<spec>"."""
    match = DEPENDS_ON.search(stderr)
    if match:
        return f"{match.group(1)} requires {match.group(2).rstrip('.,')}"
    cause = next((ln.strip() for ln in stderr.splitlines() if "cause:" in ln), "")
    return cause.replace("cause:", "").strip() or "conflicting requirements"


def fetch_json(url: str) -> dict[str, Any]:
    if not url.startswith("https://pypi.org/"):
        raise PyPIError(f"{url}: only https://pypi.org/ URLs are fetched")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        # The scheme and host are checked above, so no file: or custom scheme.
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
            data: dict[str, Any] = json.load(response)
            return data
    except (OSError, ValueError) as exc:
        raise PyPIError(f"{url}: {exc}") from exc


def stable_versions(meta: dict[str, Any]) -> list[str]:
    """Return the newest non-yanked, non-prerelease versions, newest first."""
    versions = []
    for version, files in meta.get("releases", {}).items():
        if not RELEASE.fullmatch(version):
            continue
        if not files or all(item.get("yanked") for item in files):
            continue
        versions.append(version)
    versions.sort(key=lambda v: tuple(int(p) for p in v.split(".")), reverse=True)
    return versions[:NEWEST_RELEASES]


def declares(info: dict[str, Any], target: str) -> bool:
    return f"Framework :: Django :: {target}" in (info.get("classifiers") or [])


def is_django_related(info: dict[str, Any]) -> bool:
    requires = info.get("requires_dist") or []
    classifiers = info.get("classifiers") or []
    return any(DJANGO_REQ.match(r) for r in requires) or any(
        c.startswith("Framework :: Django") for c in classifiers
    )


def install_alternative(name: str, text: str, origins: list[str], target: str) -> str:
    """Find the newest release of one package that installs with the target."""
    pinned = f"Django~={target}.0"
    try:
        meta = fetch_json(f"{PYPI}/{name}/json")
    except PyPIError as exc:
        return f"Could not query PyPI ({exc}). Check {name} releases by hand."
    for version in stable_versions(meta):
        if compile_requirements([text, f"{name}=={version}", pinned]).status == "ok":
            return (
                f"Use {name}=={version}, the newest release that installs "
                f"with Django {target}."
            )
    alternative = (
        f"No release of {name} installs with Django {target} yet. "
        "Keep the 5.2 lock, or replace the package."
    )
    if all(origin.startswith("extra:") for origin in origins):
        extras = ", ".join(o.removeprefix("extra:") for o in origins)
        alternative += f" It is only in the {extras} extra; dropping it also works."
    return alternative


def install_findings(target: str, reqs: list[Requirement]) -> list[Finding]:
    """Find every direct dependency that cannot install with the target."""
    pinned = f"Django~={target}.0"
    texts = [req.text for req in reqs]
    with concurrent.futures.ThreadPoolExecutor(PARALLEL) as pool:
        full = pool.submit(compile_requirements, [*texts, pinned])
        singles = list(
            pool.map(lambda req: compile_requirements([req.text, pinned]), reqs)
        )
    full_result = full.result()

    conflicts: dict[str, tuple[str, list[str]]] = {}
    errors: list[Finding] = []
    for req, result in zip(reqs, singles, strict=True):
        if result.status == "conflict":
            detail, origins = conflicts.get(req.text, (result.message, []))
            conflicts[req.text] = (detail, [*origins, req.origin])
        elif result.status == "error":
            errors.append(
                Finding(
                    "warning",
                    "install",
                    req.text,
                    f"Not verified: {result.message}",
                    "Rerun once uv and PyPI are reachable.",
                )
            )

    with concurrent.futures.ThreadPoolExecutor(PARALLEL) as pool:
        alternatives = list(
            pool.map(
                lambda item: install_alternative(
                    req_name(item[0]), item[0], item[1][1], target
                ),
                conflicts.items(),
            )
        )
    findings = [
        Finding(
            "blocker",
            "install",
            text,
            f"{detail}; Django {target} is outside its range.",
            alternative,
        )
        for (text, (detail, _)), alternative in zip(
            conflicts.items(), alternatives, strict=True
        )
    ]
    findings += errors
    if full_result.status == "error":
        findings.append(
            Finding(
                "warning",
                "install",
                "project",
                f"Full resolve not verified: {full_result.message}",
                "Rerun once uv and PyPI are reachable.",
            )
        )
    elif full_result.status == "conflict" and not conflicts:
        findings.append(
            Finding(
                "blocker",
                "install",
                "project",
                f"Combined requirements conflict: {full_result.message}",
                f"Keep the 5.2 lock, or relax the pins named above for Django {target}.",
            )
        )
    return findings


def locked_packages() -> list[tuple[str, str]]:
    proc = subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--all-extras",
            "--no-hashes",
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "uv export failed")
    pairs = set()
    for line in proc.stdout.splitlines():
        match = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+)", line)
        if match and normalize(match.group(1)) != "django":
            pairs.add((normalize(match.group(1)), match.group(2)))
    return sorted(pairs)


def publishes_versions(info: dict[str, Any]) -> bool:
    classifiers = info.get("classifiers") or []
    return any(VERSIONED_CLASSIFIER.match(c) for c in classifiers)


def support_scan(name: str, target: str, locked: dict[str, Any]) -> tuple[bool, str]:
    """Return (publishes per-release Django classifiers, alternative text)."""
    publishes = publishes_versions(locked)
    try:
        meta = fetch_json(f"{PYPI}/{name}/json")
    except PyPIError as exc:
        return True, f"Could not query PyPI ({exc}). Check {name} by hand."
    for version in stable_versions(meta):
        try:
            info = fetch_json(f"{PYPI}/{name}/{version}/json")["info"]
        except PyPIError as exc:
            return True, f"Could not read {name} {version} ({exc}). Check it by hand."
        if declares(info, target):
            return True, (
                f"Use {name}=={version}, the newest release that declares "
                f"Django {target}."
            )
        publishes = publishes or publishes_versions(info)
    return publishes, (
        f"No release of {name} declares Django {target} yet. Accept the risk or wait."
    )


def declared_one(pair: tuple[str, str], target: str) -> Finding | None:
    name, version = pair
    try:
        info = fetch_json(f"{PYPI}/{name}/{version}/json")["info"]
    except PyPIError as exc:
        return Finding(
            "warning",
            "declared",
            f"{name} {version}",
            f"Could not read PyPI metadata: {exc}",
            "Check the package's Framework :: Django classifiers by hand.",
        )
    if not is_django_related(info) or declares(info, target):
        return None
    publishes, alternative = support_scan(name, target, info)
    if not publishes:
        return None  # never publishes per-release classifiers; nothing to compare
    return Finding(
        "warning",
        "declared",
        f"{name} {version}",
        f"Does not declare Django {target} support (no matching classifier).",
        alternative,
    )


def declared_findings(target: str) -> list[Finding]:
    try:
        pairs = locked_packages()
    except RuntimeError as exc:
        return [
            Finding(
                "warning",
                "declared",
                "uv.lock",
                f"Could not read the locked packages: {exc}",
                "Run `uv lock --check`, then rerun this check.",
            )
        ]
    with concurrent.futures.ThreadPoolExecutor(PARALLEL) as pool:
        results = list(pool.map(lambda pair: declared_one(pair, target), pairs))
    return [finding for finding in results if finding is not None]


def python_files() -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [
            d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS
        ]
        for name in filenames:
            if name.endswith(".py"):
                found.append((Path(dirpath) / name).relative_to(REPO).as_posix())
    return sorted(found)


def probe_env(plugin_dir: Path, out: Path) -> dict[str, str]:
    paths = [str(plugin_dir), os.environ.get("PYTHONPATH", "")]
    return {
        **os.environ,
        "DJANGO_READ_DOT_ENV": "0",
        "PYTHONPATH": os.pathsep.join(p for p in paths if p),
        "DJANGO_UPGRADE_PROBE_OUT": str(out),
    }


def probe_records(target: str) -> list[dict[str, Any]] | str:
    """Return warnings recorded by the suite, or an explanation of the failure."""
    with tempfile.TemporaryDirectory() as tmp:
        plugin_dir = Path(tmp)
        (plugin_dir / "django_upgrade_probe.py").write_text(
            PROBE_PLUGIN, encoding="utf-8"
        )
        out = plugin_dir / "warnings.json"
        cmd = [sys.executable, "-m", "pytest", "-q", "--no-cov"]
        cmd += ["-p", "no:cacheprovider", "-p", "django_upgrade_probe"]
        for category in REMOVAL_WARNINGS[target]:
            cmd += ["-W", f"always::django.utils.deprecation.{category}"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=REPO,
                env=probe_env(plugin_dir, out),
                capture_output=True,
                text=True,
                check=False,
                timeout=1800,
            )
        except subprocess.TimeoutExpired:
            return "the warning scan timed out"
        if not out.exists():
            return f"the warning scan wrote no results (pytest exit {proc.returncode})"
        records: list[dict[str, Any]] = json.loads(out.read_text(encoding="utf-8"))
        return records


def code_findings(target: str) -> list[Finding]:
    """Run the suite on the current Django and keep first-party deprecations."""
    records = probe_records(target)
    if isinstance(records, str):
        return [
            Finding(
                "warning",
                "code",
                "test suite",
                f"Not verified: {records}.",
                "Fix the test run (uv run pytest), then rerun this check.",
            )
        ]
    categories = set(REMOVAL_WARNINGS[target])
    findings: dict[tuple[str, int, str], Finding] = {}
    for record in records:
        if record["category"] not in categories:
            continue
        try:
            rel = Path(record["filename"]).resolve().relative_to(REPO)
        except (ValueError, OSError):
            continue
        if rel.parts[0].startswith(".") or rel.parts[0] in SKIP_DIRS:
            continue
        key = (rel.as_posix(), record["lineno"], record["category"])
        match = REMOVED_IN.search(record["category"])
        removed = f"{match.group(1)}.{match.group(2)}" if match else target
        findings.setdefault(
            key,
            Finding(
                "blocker",
                "code",
                f"{key[0]}:{key[1]}",
                f"Uses a feature removed in Django {removed} ({key[2]}).",
                f"Follow the Django message: {record['message']}",
            ),
        )
    return [findings[key] for key in sorted(findings)]


def django_upgrade(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uvx", "--from", DJANGO_UPGRADE, "django-upgrade", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


def fixer_delta(target: str) -> list[str]:
    """Return files that still need a fixer after the prior release's fixers.

    django-upgrade runs every fixer up to the target. Applying the prior
    release's fixers to a copy of the tree first leaves only the fixers that
    the target adds.
    """
    files = python_files()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel in files:
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dest)
        base = django_upgrade(["--target-version", BASELINE[target], *files], root)
        if base.returncode not in (0, 1):
            raise RuntimeError(f"django-upgrade exited {base.returncode} on the copy")
        check = django_upgrade(["--check", "--target-version", target, *files], root)
    if check.returncode not in (0, 1):
        raise RuntimeError(f"django-upgrade exited {check.returncode}")
    # django-upgrade prints "Would rewrite" to stderr.
    output = (check.stdout + check.stderr).splitlines()
    return [
        line.removeprefix("Would rewrite ").strip()
        for line in output
        if line.startswith("Would rewrite ")
    ]


def upgrade_fixer_findings(target: str) -> list[Finding]:
    try:
        paths = fixer_delta(target)
    except RuntimeError as exc:
        return [
            Finding(
                "warning",
                "django-upgrade",
                "fixers",
                f"Not verified: {exc}.",
                f"Run uvx --from {DJANGO_UPGRADE} django-upgrade --check "
                f"--target-version {target} by hand.",
            )
        ]
    return [
        Finding(
            "warning",
            "django-upgrade",
            path,
            f"Django {target} fixers would rewrite this file after the "
            f"{BASELINE[target]} fixers.",
            f"Run uvx --from {DJANGO_UPGRADE} django-upgrade --target-version "
            f"{target} {path}, then review the diff.",
        )
        for path in paths
    ]


def uv_django_version(spec: str, env: dict[str, str]) -> str:
    proc = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "--with",
            spec,
            "python",
            "-c",
            "import django; print(django.get_version())",
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    return proc.stdout.strip()


def junit_totals(xml: Path) -> dict[str, int]:
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    # The file is the JUnit report this script asked pytest to write.
    for suite in ET.parse(xml).getroot().iter("testsuite"):  # nosec B314
        for key in totals:
            totals[key] += int(suite.get(key, "0"))
    return totals


def test_findings(target: str) -> tuple[list[Finding], dict[str, Any]]:
    """Run the suite on the target Django through a uv overlay."""
    spec = f"Django~={target}.0"
    env = {**os.environ, "DJANGO_READ_DOT_ENV": "0"}
    version = uv_django_version(spec, env)
    if not version.startswith(f"{target}."):
        finding = Finding(
            "blocker",
            "tests",
            spec,
            f"The test run loaded Django {version or 'nothing'}, not {target}.",
            "Fix the uv overlay, then rerun with --run-tests.",
        )
        return [finding], {"django": version}
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "junit.xml"
        subprocess.run(
            [
                "uv",
                "run",
                "--no-sync",
                "--with",
                spec,
                "python",
                "-m",
                "pytest",
                "-q",
                "--no-cov",
                "-p",
                "no:cacheprovider",
                f"--junitxml={xml}",
            ],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=3600,
        )
        if not xml.exists():
            finding = Finding(
                "blocker",
                "tests",
                spec,
                "The suite produced no test report on the target Django.",
                "Run the suite by hand on the target and fix the failure.",
            )
            return [finding], {"django": version}
        totals = junit_totals(xml)
    summary: dict[str, Any] = {"django": version, **totals}
    broken = totals["failures"] + totals["errors"]
    if not broken:
        return [], summary
    finding = Finding(
        "blocker",
        "tests",
        f"Django {target} suite",
        f"{broken} of {totals['tests']} tests fail on Django {target}.",
        "Fix the failing tests, then rerun with --run-tests.",
    )
    return [finding], summary


@dataclasses.dataclass
class Report:
    target: str
    current: str
    findings: list[Finding]
    tests: dict[str, Any] | None

    @property
    def verdict(self) -> str:
        if any(f.severity == "blocker" for f in self.findings):
            return "BLOCKED"
        if self.findings:
            return "SAFE WITH WARNINGS"
        return "SAFE"

    def as_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "current": self.current,
            "verdict": self.verdict,
            "findings": [dataclasses.asdict(f) for f in self.findings],
            "tests": self.tests,
        }

    def as_text(self) -> str:
        lines = [
            f"Django upgrade check: {self.current} -> {self.target}",
            f"Verdict: {self.verdict}",
            "",
        ]
        for severity, title in (("blocker", "Blockers"), ("warning", "Warnings")):
            items = [f for f in self.findings if f.severity == severity]
            lines.append(f"{title}: {len(items)}")
            for item in items:
                lines.append(f"  - [{item.source}] {item.subject}: {item.detail}")
                lines.append(f"    Alternative: {item.alternative}")
            lines.append("")
        if self.tests is None:
            lines.append(f"Tests on Django {self.target}: not run (--run-tests).")
        else:
            lines.append(f"Tests on Django {self.target}: {self.tests}")
        return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("target", help="target Django release: 6.0 or 6.1")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument(
        "--run-tests", action="store_true", help="also run the suite on the target"
    )
    args = parser.parse_args(argv)

    if args.target not in SUPPORTED_TARGETS:
        print(
            f"Unsupported target {args.target!r}. Use one of: "
            f"{', '.join(SUPPORTED_TARGETS)}.",
            file=sys.stderr,
        )
        return 3
    current = importlib.metadata.version("django")
    if release_of(current) >= release_of(args.target):
        print(
            f"The environment runs Django {current}. Run this check from the "
            "Django 5.2 environment.",
            file=sys.stderr,
        )
        return 3

    findings: list[Finding] = []
    findings += install_findings(args.target, load_requirements())
    findings += declared_findings(args.target)
    findings += code_findings(args.target)
    findings += upgrade_fixer_findings(args.target)
    tests = None
    if args.run_tests:
        test_found, tests = test_findings(args.target)
        findings += test_found

    report = Report(args.target, current, findings, tests)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(report.as_text())
    return EXIT_CODES[report.verdict]


if __name__ == "__main__":
    sys.exit(main())
