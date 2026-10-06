#!/usr/bin/env python3
"""Version drift gate: one version per tool across the project config.

``pyproject.toml`` and ``uv.lock`` are the source of truth. The gate reads every
place that also names a version and fails when two places disagree:

- python:   ``requires-python``, ruff ``target-version``, mypy/ty
            ``python_version``, ``.python-version``, every ``python:X.Y`` base
            image and Dockerfile ``ARG PYTHON_VERSION``, and the pre-commit
            ``default_language_version``.
- python image: every ``FROM python:`` must be
            ``python:${PYTHON_VERSION}-...@${PYTHON_IMAGE_DIGEST}``, with an
            exact ``X.Y.Z`` version and a ``sha256:`` digest, identical in
            every Dockerfile. A floating tag such as ``python:3.13-slim`` fails.
- uv:       every ``ghcr.io/astral-sh/uv:<version>`` image in a Dockerfile, and
            ``[tool.uv] required-version``. An unpinned installer script fails.
- postgres: the major version of every Postgres image in Compose, including
            the default in ``${VAR:-image}``, and any ``*IMAGE=`` override in
            ``.env.example``.
- valkey:   every cache image in Compose (a ``redis:`` image is drift too).
- images:   a Compose ``image: ${VAR}`` with no default fails (unpinned).
- hooks:    every pre-commit hook is ``repo: local``. A hook that runs a tool
            through ``uvx <pkg>==<v>`` or ``bunx <pkg>@<v>`` must pin it, use
            one version per package, and must not bypass ``uv.lock`` for a
            locked package (run those with ``uv run <tool>``).

Values are read from the files on each run; nothing is hard-coded, so a version
bump only has to land in every file at once.

Usage:
    python scripts/check_version_drift.py

Exit: 0 = no drift, 1 = drift or an unpinned version
"""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Files that may name a version. Paths are relative to the project root.
DOCKERFILE_GLOBS = ("Dockerfile*", "deploy/docker/Dockerfile*")
COMPOSE_GLOBS = ("docker-compose*.yml", "compose*.yml")
PRE_COMMIT = ".pre-commit-config.yaml"

#: Hook entries that run a tool outside the project environment.
UVX_RUN = re.compile(
    r"\buvx\s+(?:--from\s+)?([A-Za-z0-9_.\[\]-]+?)(?:==(\S+))?(?:\s|$)"
)
BUNX_RUN = re.compile(r"\bbunx\s+((?:@[\w.-]+/)?[\w.-]+)(?:@(\d\S*))?(?:\s|$)")

POSTGRES_IMAGE = re.compile(
    r"^(?:postgres|(?:[\w.-]+/)?pgvector/pgvector|postgis/postgis):(?:pg)?(\d+)"
)
CACHE_IMAGE = re.compile(r"^(?:docker\.io/)?(valkey/valkey|redis):(\d+)")


@dataclass(frozen=True)
class Finding:
    """One version as written in one place."""

    source: str
    value: str


def _rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _files(globs: tuple[str, ...]) -> list[Path]:
    found = {path for pattern in globs for path in PROJECT_ROOT.glob(pattern)}
    return sorted(path for path in found if path.is_file())


def _lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    return list(enumerate(text.splitlines(), start=1))


def _major_minor(version: str) -> str:
    return ".".join(version.split(".")[:2])


def python_versions(pyproject: dict) -> list[Finding]:
    """Every Python major.minor the project names."""
    found: list[Finding] = []
    requires = pyproject.get("project", {}).get("requires-python", "")
    if match := re.search(r"(\d+\.\d+)", requires):
        found.append(Finding("pyproject.toml requires-python", match.group(1)))
    tool = pyproject.get("tool", {})
    target = tool.get("ruff", {}).get("target-version", "")
    if match := re.fullmatch(r"py(\d)(\d+)", target):
        found.append(Finding("pyproject.toml [tool.ruff]", f"{match[1]}.{match[2]}"))
    for section, key in (("mypy", "python_version"), ("ty", "python-version")):
        if value := tool.get(section, {}).get(key):
            found.append(Finding(f"pyproject.toml [tool.{section}]", str(value)))
    if (pinned := PROJECT_ROOT / ".python-version").is_file():
        value = pinned.read_text(encoding="utf-8").strip()
        found.append(Finding(".python-version", _major_minor(value)))

    image = re.compile(r"(?:\bpython:|astral-sh/uv:\S*?python)(\d+\.\d+)")
    arg = re.compile(r"\s*ARG\s+PYTHON_VERSION=(\d+\.\d+)")
    for path in _files(DOCKERFILE_GLOBS):
        for number, line in _lines(path):
            if line.lstrip().upper().startswith(("FROM", "COPY", "ARG")):
                for match in image.finditer(line):
                    found.append(Finding(f"{_rel(path)}:{number}", match.group(1)))
            if match := arg.match(line):
                found.append(Finding(f"{_rel(path)}:{number}", match.group(1)))

    pre_commit = PROJECT_ROOT / PRE_COMMIT
    if pre_commit.is_file():
        for number, line in _lines(pre_commit):
            if match := re.match(r"\s+python:\s*python(\d+\.\d+)", line):
                found.append(Finding(f"{PRE_COMMIT}:{number}", match.group(1)))
    return found


def python_images() -> tuple[list[Finding], list[Finding], list[str]]:
    """Exact Python base image pins (version, digest) plus policy errors."""
    versions: list[Finding] = []
    digests: list[Finding] = []
    errors: list[str] = []
    version_arg = re.compile(r"\s*ARG\s+PYTHON_VERSION=(\S+)")
    digest_arg = re.compile(r"\s*ARG\s+PYTHON_IMAGE_DIGEST=(\S+)")
    pinned_from = re.compile(
        r"\s*FROM\s+python:\$\{PYTHON_VERSION\}-\S+@\$\{PYTHON_IMAGE_DIGEST\}\s"
    )
    for path in _files(DOCKERFILE_GLOBS):
        uses_args = False
        has_version = has_digest = False
        for number, line in _lines(path):
            source = f"{_rel(path)}:{number}"
            if match := version_arg.match(line):
                has_version = True
                versions.append(Finding(source, match.group(1)))
                if not re.fullmatch(r"\d+\.\d+\.\d+", match.group(1)):
                    errors.append(f"python image: {source} needs an exact X.Y.Z")
            elif match := digest_arg.match(line):
                has_digest = True
                digests.append(Finding(source, match.group(1)))
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", match.group(1)):
                    errors.append(f"python image: {source} needs a sha256 digest")
            elif re.match(r"\s*FROM\s+python:", line, re.IGNORECASE):
                if pinned_from.match(line + " "):
                    uses_args = True
                else:
                    errors.append(
                        f"python image: {source} uses a floating tag; use "
                        "python:${PYTHON_VERSION}-<variant>@${PYTHON_IMAGE_DIGEST}"
                    )
        if uses_args and not (has_version and has_digest):
            errors.append(
                f"python image: {_rel(path)} needs ARG PYTHON_VERSION and "
                "ARG PYTHON_IMAGE_DIGEST before its first FROM"
            )
    return versions, digests, errors


def uv_versions(pyproject: dict) -> tuple[list[Finding], list[str]]:
    """Every pinned uv version, plus errors for unpinned installs."""
    found: list[Finding] = []
    errors: list[str] = []
    pinned = re.compile(r"astral-sh/uv:(\d+\.\d+\.\d+)")
    installer = re.compile(r"astral\.sh/uv/(?:(\d+\.\d+\.\d+)/)?install\.sh")
    for path in _files(DOCKERFILE_GLOBS):
        for number, line in _lines(path):
            source = f"{_rel(path)}:{number}"
            for match in pinned.finditer(line):
                found.append(Finding(source, match.group(1)))
            for match in installer.finditer(line):
                if match.group(1):
                    found.append(Finding(source, match.group(1)))
                else:
                    errors.append(f"uv: {source} installs uv without a version pin")

    required = pyproject.get("tool", {}).get("uv", {}).get("required-version")
    if required:
        from packaging.specifiers import SpecifierSet

        spec = SpecifierSet(required)
        for item in found:
            if item.value not in spec:
                errors.append(
                    f"uv: {item.source} pins {item.value}, outside "
                    f"[tool.uv] required-version {required!r}"
                )
    return found, errors


def compose_images(pattern: re.Pattern[str]) -> list[Finding]:
    """Versions of the Compose images (and `.env.example` overrides) for *pattern*."""
    found: list[Finding] = []
    for path in _files(COMPOSE_GLOBS):
        for number, line in _lines(path):
            image = re.match(r"\s*image:\s*[\"']?([^\s\"']+)", line)
            # `${POSTGRES_IMAGE:-postgres:17-alpine}` drifts through its default.
            name = re.sub(r"^\$\{\w+:?-(.+)\}$", r"\1", image.group(1)) if image else ""
            if name and (match := pattern.match(name)):
                found.append(
                    Finding(f"{_rel(path)}:{number}", " ".join(match.groups()))
                )
    # A documented override such as POSTGRES_IMAGE=pgvector/pgvector:pg17.
    env_example = PROJECT_ROOT / ".env.example"
    if env_example.is_file():
        for number, line in _lines(env_example):
            value = re.match(r"\s*#?\s*\w*IMAGE\s*=\s*[\"']?([^\s\"'#]+)", line)
            if value and (match := pattern.match(value.group(1))):
                found.append(
                    Finding(f".env.example:{number}", " ".join(match.groups()))
                )
    return found


def unpinned_images() -> list[str]:
    """Compose images that come only from a variable, with no default."""
    errors: list[str] = []
    for path in _files(COMPOSE_GLOBS):
        for number, line in _lines(path):
            if re.match(r"\s*image:\s*[\"']?\$\{?\w+\}?[\"']?\s*$", line):
                errors.append(
                    f"images: {_rel(path)}:{number} has no default image; "
                    "use ${VAR:-image:tag} so the version can be checked"
                )
    return errors


def locked_versions() -> dict[str, str]:
    """Package name to locked version, from ``uv.lock``."""
    lock = PROJECT_ROOT / "uv.lock"
    if not lock.is_file():
        return {}
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    return {pkg["name"]: pkg["version"] for pkg in data.get("package", [])}


def _normalize(package: str) -> str:
    return re.sub(r"[-_.]+", "-", re.sub(r"\[.*\]$", "", package)).lower()


def hook_tools(locked: dict[str, str]) -> tuple[dict[str, list[Finding]], list[str]]:
    """Tool versions pinned in pre-commit entries, plus policy errors."""
    path = PROJECT_ROOT / PRE_COMMIT
    if not path.is_file():
        return {}, []
    tools: dict[str, list[Finding]] = {}
    errors: list[str] = []
    for number, line in _lines(path):
        source = f"{PRE_COMMIT}:{number}"
        repo = re.match(r"\s*-\s*repo:\s*(\S+)", line)
        if repo and repo.group(1) not in {"local", "meta"}:
            errors.append(f"hooks: {source} uses {repo.group(1)}; use repo: local")
        if not re.match(r"\s*entry:", line):
            continue
        for pattern in (UVX_RUN, BUNX_RUN):
            for match in pattern.finditer(line):
                name, version = _normalize(match.group(1)), match.group(2)
                if not version:
                    errors.append(f"hooks: {source} runs {name} without a version")
                elif pattern is UVX_RUN and name in locked:
                    errors.append(
                        f"hooks: {source} runs {name} {version} outside uv.lock "
                        f"({locked[name]}); use `uv run {name}`"
                    )
                else:
                    tools.setdefault(name, []).append(Finding(source, version))
    return tools, errors


def compare(tool: str, findings: list[Finding]) -> list[str]:
    """Return a drift error when *findings* name more than one version."""
    by_value: dict[str, list[str]] = {}
    for item in findings:
        by_value.setdefault(item.value, []).append(item.source)
    if len(by_value) <= 1:
        return []
    detail = "; ".join(
        f"{value} in {', '.join(sources)}" for value, sources in by_value.items()
    )
    return [f"{tool}: {len(by_value)} different versions: {detail}"]


def main() -> int:
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    uv_found, errors = uv_versions(pyproject)
    hooks, hook_errors = hook_tools(locked_versions())
    errors.extend(hook_errors)
    errors.extend(unpinned_images())
    image_versions, image_digests, image_errors = python_images()
    errors.extend(image_errors)
    checks = {
        "python": python_versions(pyproject),
        "python image": image_versions,
        "python image digest": image_digests,
        "uv": uv_found,
        "postgres": compose_images(POSTGRES_IMAGE),
        "valkey": compose_images(CACHE_IMAGE),
        **{f"hook {name}": findings for name, findings in sorted(hooks.items())},
    }
    for tool, findings in checks.items():
        errors.extend(compare(tool, findings))

    for tool, findings in checks.items():
        values = ", ".join(sorted({item.value for item in findings})) or "not set"
        print(f"  {tool:<26} {values} ({len(findings)} sources)")
    if errors:
        print("\nVersion drift:")
        for error in errors:
            print(f"  FAIL {error}")
        return 1
    print("\n  OK: no version drift")
    return 0


if __name__ == "__main__":
    sys.exit(main())
