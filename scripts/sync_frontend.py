#!/usr/bin/env python3
"""Report how a frontend repo lines up with this backend.

Read-only on both repos. It runs no network commands and no package
manager. Three checks:

1. JOURNEYS: the sync report with ``JOURNEYS_E2E_DIR=FRONTEND/e2e`` and
   ``JOURNEYS_E2E_REPORT=FRONTEND/test-results/journeys.json``.
2. CONTRACT: find the frontend's copy of the OpenAPI document (the input of
   an ``openapi`` script in ``package.json``, ``openapi-ts.config.*``, or a
   common location) and compare it with ``docs/openapi/openapi.json``.
3. MATTSTACK: when ``mattstack`` is on PATH and the frontend has a sibling
   ``backend/``, print the ``mattstack sync check`` command.

Usage:
    uv run python scripts/sync_frontend.py ~/dev/react-vite-boilerplate
    uv run python scripts/sync_frontend.py ../frontend --check

Exit: 0 by default. With ``--check``: 1 on a journeys error or contract
drift, else 0. Exit 2 when FRONTEND is not a directory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import sys
from dataclasses import dataclass, field
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

CONTRACT = ROOT / "docs" / "openapi" / "openapi.json"
COMMON_COPIES = (
    "backend/docs/openapi/openapi.json",
    "src/types/generated/schema.json",
    "openapi.json",
)
OPENAPI_TS_CONFIGS = (
    "openapi-ts.config.ts",
    "openapi-ts.config.mts",
    "openapi-ts.config.js",
    "openapi-ts.config.mjs",
)
CONFIG_INPUT = re.compile(r"""input\s*:\s*['"]([^'"]+)['"]""")
INPUT_FLAGS = ("-i", "--input")
OUTPUT_FLAGS = ("-o", "--output")
HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
MAX_DIFF_LINES = 20
MAX_ISSUE_LINES = 10
SUGGESTED_COPY = "src/types/generated/schema.json"
SUGGESTED_SCRIPT = f"openapi-ts -i {SUGGESTED_COPY} -o src/api/generated"


@dataclass(frozen=True)
class Candidate:
    """A place the frontend may keep its contract copy."""

    path: Path
    source: str


@dataclass
class ContractResult:
    """Outcome of the contract comparison."""

    drift: bool = False
    lines: list[str] = field(default_factory=list)


# --- journeys -------------------------------------------------------------


def journeys_report(frontend: Path) -> SyncReport:
    """Build the journeys report against the frontend's e2e suite."""
    environ = dict(os.environ)
    environ["JOURNEYS_E2E_DIR"] = str(frontend / "e2e")
    environ["JOURNEYS_E2E_REPORT"] = str(frontend / "test-results" / "journeys.json")
    return build_report(spec_paths(ROOT, environ))


def _issue_line(issue: Issue) -> str:
    where = f" ({issue.path})" if issue.path else ""
    return f"    {issue.code}: {issue.message}{where}"


def print_journeys(report: SyncReport) -> None:
    paths = report.paths
    e2e = "found" if report.e2e_dir_exists else "missing"
    results = "found" if report.report_exists else "missing"
    print("JOURNEYS")
    print(f"  e2e dir {paths.e2e_dir} ({e2e})")
    print(f"  report  {paths.e2e_report} ({results})")
    print(
        f"  {len(report.features)} features, {len(report.journeys)} journeys, "
        f"{report.verified_journeys} verified"
    )
    print(
        f"  {len(report.errors)} errors, {len(report.warnings)} warnings, "
        f"{len(report.gaps)} gaps"
    )
    for issue in report.errors[:MAX_ISSUE_LINES]:
        print(_issue_line(issue))
    hidden = len(report.errors) - MAX_ISSUE_LINES
    if hidden > 0:
        print(f"    ... {hidden} more errors")
    if report.errors or report.warnings or report.gaps:
        print(
            "  full list: "
            f"JOURNEYS_E2E_DIR={shlex.quote(str(paths.e2e_dir))} "
            f"JOURNEYS_E2E_REPORT={shlex.quote(str(paths.e2e_report))} "
            "uv run python scripts/check_journeys.py"
        )


# --- contract discovery ---------------------------------------------------


def _script_inputs(command: str) -> list[str]:
    """Return the input paths of one ``openapi`` package.json script."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    inputs: list[str] = []
    positional: list[str] = []
    skip_next = False
    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token in INPUT_FLAGS and index + 1 < len(tokens):
            inputs.append(tokens[index + 1])
            skip_next = True
        elif token.startswith("--input="):
            inputs.append(token.split("=", 1)[1])
        elif token in OUTPUT_FLAGS:
            skip_next = True
        elif token.endswith((".json", ".yaml", ".yml")) and not token.startswith("-"):
            positional.append(token)
    return inputs or positional


def _package_scripts(frontend: Path) -> dict[str, str]:
    package = frontend / "package.json"
    if not package.is_file():
        return {}
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return {}
    return {str(k): str(v) for k, v in scripts.items() if isinstance(v, str)}


def find_candidates(frontend: Path) -> tuple[list[Candidate], list[str]]:
    """Return local contract candidates and remote inputs (not fetched)."""
    found: list[Candidate] = []
    remote: list[str] = []

    def add(raw: str, source: str) -> None:
        if raw.startswith(("http://", "https://")):
            remote.append(f"{raw} ({source})")
            return
        found.append(Candidate((frontend / raw).resolve(), source))

    for name, command in _package_scripts(frontend).items():
        if "openapi" in command.lower():
            for raw in _script_inputs(command):
                add(raw, f"package.json script {name!r}")
    for config in OPENAPI_TS_CONFIGS:
        path = frontend / config
        if path.is_file():
            for raw in CONFIG_INPUT.findall(path.read_text(encoding="utf-8")):
                add(raw, config)
    for raw in COMMON_COPIES:
        add(raw, "common location")
    if (frontend.parent / "backend").is_dir():
        add(f"../{COMMON_COPIES[0]}", "monorepo sibling backend/")

    unique: dict[Path, Candidate] = {}
    for candidate in found:
        unique.setdefault(candidate.path, candidate)
    return list(unique.values()), remote


# --- contract comparison --------------------------------------------------


def _operations(spec: dict[str, object]) -> dict[str, dict[str, str]]:
    """Map path -> method -> operationId ("" when absent)."""
    paths = spec.get("paths")
    result: dict[str, dict[str, str]] = {}
    if not isinstance(paths, dict):
        return result
    for path, item in paths.items():
        methods: dict[str, str] = {}
        if isinstance(item, dict):
            for method, operation in item.items():
                if method in HTTP_METHODS and isinstance(operation, dict):
                    methods[method] = str(operation.get("operationId", ""))
        result[str(path)] = methods
    return result


def _schema_names(spec: dict[str, object]) -> set[str]:
    components = spec.get("components")
    if not isinstance(components, dict):
        return set()
    schemas = components.get("schemas")
    return {str(name) for name in schemas} if isinstance(schemas, dict) else set()


def diff_lines(canonical: dict[str, object], copy: dict[str, object]) -> list[str]:
    """Describe how the copy differs from the canonical contract."""
    ours, theirs = _operations(canonical), _operations(copy)
    lines = [
        f"  + {path} (in backend, missing from copy)"
        for path in sorted(ours.keys() - theirs.keys())
    ]
    lines += [
        f"  - {path} (in copy, gone from backend)"
        for path in sorted(theirs.keys() - ours.keys())
    ]
    for path in sorted(ours.keys() & theirs.keys()):
        for method in sorted(ours[path].keys() | theirs[path].keys()):
            new = ours[path].get(method, "(none)") or "(no id)"
            old = theirs[path].get(method, "(none)") or "(no id)"
            if new != old:
                lines.append(f"  ~ {method.upper()} {path}: operationId {old} -> {new}")
    ours_schemas, theirs_schemas = _schema_names(canonical), _schema_names(copy)
    added, removed = ours_schemas - theirs_schemas, theirs_schemas - ours_schemas
    if added or removed:
        lines.append(f"  components.schemas: +{len(added)} -{len(removed)}")
    if not lines:
        lines.append("  no path or operationId changes; schemas or details differ")
    if len(lines) > MAX_DIFF_LINES:
        hidden = len(lines) - (MAX_DIFF_LINES - 1)
        lines = [*lines[: MAX_DIFF_LINES - 1], f"  ... {hidden} more lines"]
    return lines


def _load_json(path: Path) -> dict[str, object] | str:
    """Return the parsed object, or an error message."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f"cannot read {path}: {exc}"
    if not isinstance(data, dict):
        return f"{path} is not a JSON object"
    return data


def _canonical(data: dict[str, object]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def compare_contract(frontend: Path) -> ContractResult:
    """Compare every existing contract copy with this repo's contract."""
    result = ContractResult()
    canonical = _load_json(CONTRACT)
    if isinstance(canonical, str):
        result.lines.append(f"  {canonical}; run `just openapi`")
        result.drift = True
        return result
    candidates, remote = find_candidates(frontend)
    for entry in remote:
        result.lines.append(f"  remote input {entry}: not fetched (no network)")
    copies = [c for c in candidates if c.path.is_file()]
    if not copies:
        checked = ", ".join(COMMON_COPIES)
        result.lines.append(
            f"  copy: missing (checked package.json openapi scripts, "
            f"openapi-ts.config.*, {checked})"
        )
        result.lines.append("  add one:")
        result.lines.append(
            f"    mkdir -p {shlex.quote(str(frontend / Path(SUGGESTED_COPY).parent))}"
            f" && cp {shlex.quote(str(CONTRACT))} "
            f"{shlex.quote(str(frontend / SUGGESTED_COPY))}"
        )
        result.lines.append(
            f"    cd {shlex.quote(str(frontend))} && "
            "bun add -D --exact @hey-api/openapi-ts"
        )
        result.lines.append(
            f'    package.json scripts: "api:generate": "{SUGGESTED_SCRIPT}"'
        )
        return result
    for copy in copies:
        result.lines.append(f"  copy {copy.path} ({copy.source})")
        if copy.path == CONTRACT.resolve():
            result.lines.append("    reads this repo's contract directly: in sync")
            continue
        data = _load_json(copy.path)
        if isinstance(data, str):
            result.drift = True
            result.lines.append(f"    {data}")
            continue
        if _canonical(data) == _canonical(canonical):
            result.lines.append("    in sync with docs/openapi/openapi.json")
            continue
        result.drift = True
        result.lines.append("    DRIFT against docs/openapi/openapi.json:")
        result.lines.extend(f"  {line}" for line in diff_lines(canonical, data))
        result.lines.append(
            f"    refresh: cp {shlex.quote(str(CONTRACT))} "
            f"{shlex.quote(str(copy.path))}, then regenerate the client"
        )
    return result


# --- mattstack ------------------------------------------------------------


def mattstack_line(frontend: Path) -> str:
    """Say whether ``mattstack sync check`` applies. Never runs it."""
    project = frontend.parent
    if not (project / "backend").is_dir():
        return "  not a mattstack monorepo frontend (no sibling backend/)"
    if shutil.which("mattstack") is None:
        return "  monorepo layout, but mattstack is not on PATH"
    return (
        "  monorepo layout: verify the generated client with "
        f"`mattstack sync check -p {shlex.quote(str(project))}`"
    )


# --- entry point ----------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report journeys and OpenAPI drift for a frontend repo."
    )
    parser.add_argument("frontend", type=Path, help="path to the frontend repo")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 on a journeys error or contract drift",
    )
    args = parser.parse_args(argv)
    frontend = args.frontend.expanduser().resolve()
    if not frontend.is_dir():
        print(f"sync-frontend: {frontend} is not a directory", file=sys.stderr)
        return 2

    print(f"SYNC-FRONTEND: {frontend}")
    report = journeys_report(frontend)
    print_journeys(report)

    print("CONTRACT")
    contract = compare_contract(frontend)
    for line in contract.lines:
        print(line)

    print("MATTSTACK")
    print(mattstack_line(frontend))

    failed = bool(report.errors) or contract.drift
    status = "FAIL" if failed else "OK"
    print(
        f"SYNC-FRONTEND: {status} ({len(report.errors)} journeys errors, "
        f"contract {'drift' if contract.drift else 'no drift'})"
    )
    return 1 if args.check and failed else 0


if __name__ == "__main__":
    sys.exit(main())
