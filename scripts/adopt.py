#!/usr/bin/env python3
"""Show and copy portable boilerplate modules into another Django backend.

Run it from this boilerplate checkout. ``--target`` is the other backend (the
directory that holds its ``manage.py``). The target records what it adopted in
``<target>/.boilerplate.toml``. See docs/ADOPTING_UPDATES.md.

Usage:
    python scripts/adopt.py list
    python scripts/adopt.py status --target ../my-api [--since 1.12.0]
    python scripts/adopt.py diff journeys --target ../my-api [--patch]
    python scripts/adopt.py apply journeys --target ../my-api [--dry-run] [--force]

The script copies files and prints the wiring (settings, URLs, justfile,
gates). It never edits code in the target and never copies secrets.

Exit: 0 = success, 1 = refused (conflict or dirty file), 2 = usage or target error
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ".boilerplate.toml"
SECRET_PATTERNS = (".env*", "*.pem", "*.key", "secrets*")
SKIP_NAMES = ("__pycache__", "node_modules", "*.pyc", ".DS_Store")
SCRIPT = "uv run python scripts/adopt.py"


class AdoptError(Exception):
    """A target or manifest problem. The command exits with status 2."""


@dataclass(frozen=True)
class Step:
    """One wiring step, printed for a human or an agent to apply by hand."""

    title: str
    where: str
    snippet: str = ""
    source: tuple[str, str] | None = None  # (file in this repo, markdown heading)


@dataclass(frozen=True)
class Seed:
    """A starter file, written only when the target has none of ``unless``."""

    path: str
    content: str
    unless: tuple[str, ...]


@dataclass(frozen=True)
class Module:
    """A portable module: files to copy plus the wiring to print."""

    name: str
    summary: str
    versions: tuple[str, ...]  # CHANGELOG versions; the first introduced it
    paths: tuple[str, ...]  # files or directories in this repo
    steps: tuple[Step, ...]
    seeds: tuple[Seed, ...] = ()
    docs: tuple[str, ...] = ()


# Manifest: wiring snippets mirror this repo's settings, urls.py and justfile.

PYYAML = Step("Add the YAML dependency", "pyproject.toml", "uv add pyyaml")
UNFOLD_PREREQ = Step(
    "Prerequisite: django-unfold renders the admin page",
    "settings",
    'uv add django-unfold   # then put "unfold" before "django.contrib.admin"',
)


def _app_step(app: str, comment: str) -> Step:
    return Step("Install the app", "settings INSTALLED_APPS", f'"{app}",  # {comment}')


def _urls_step(imports: str, routes: str) -> Step:
    body = "\n".join(f"    {route}" for route in routes.splitlines())
    return Step(
        "Add the URLs before the admin catch-all",
        "root urls.py",
        f"{imports}\n\nurlpatterns = [\n{body}\n"
        '    path("admin/", admin.site.urls),  # the catch-all stays below\n]',
    )


def _sidebar_step(title: str, icon: str, url_name: str) -> Step:
    return Step(
        "Add the sidebar item",
        'UNFOLD["SIDEBAR"]["navigation"] items',
        f'{{"title": "{title}", "icon": "{icon}", '
        f'"link": reverse_lazy("{url_name}")}},',
    )


def _recipe_step(comment: str, recipe: str, command: str) -> Step:
    return Step("Add the recipe", "justfile", f"# {comment}\n{recipe}:\n    {command}")


def _gate_step(name: str, command: str) -> Step:
    method = name.lower()
    args = ", ".join(json.dumps(part) for part in command.split())
    return Step(
        f"Add the {name} gate (boilerplate gauntlet; else your own gate runner)",
        "scripts/gauntlet.py",
        f'gates["{method}"] = self._gate_{method}\n\n'
        f"def _gate_{method}(self) -> GateResult:\n"
        f'    return self.run_gate(\n        "{name}", [{args}]\n    )',
    )


def _packages_step(app: str) -> Step:
    return Step(
        f"Add {app!r} to the package lists",
        "pyproject.toml",
        f'[tool.hatch.build.targets.wheel]  packages = [..., "{app}"]\n'
        f'[tool.ruff.lint.isort]            known-first-party = [..., "{app}"]\n'
        f'[tool.pytest.ini_options]         testpaths = [..., "{app}"]',
    )


FEATURES_SEED = """\
# Features

This file lists the product features, grouped by area. A checked box `[x]`
means "verified by a passing Playwright journey". It never means "the code
exists". See [README.md](README.md) for the rules.

## Accounts

- [ ] F-001 Sign in with email and password
"""

JOURNEY_SEED = """\
---
id: J-001
title: Sign in
actor: Visitor
status: draft
steps:
  - id: S1
    title: Sign in
    story: As a visitor, I want to sign in, so that I reach my account.
    features: [F-001]
    acceptance:
      - A valid email and password open the signed-in home page.
---

## Goal

Replace this example with the first real journey of the product.
"""

STAFF_FIXTURE = """\
@pytest.fixture
def staff_user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        username="staff", email="staff@example.com",
        password="unused-Pass-1", is_staff=True,
    )"""

ATLAS_SETTINGS = """\
ATLAS_ENABLED = env.bool("ATLAS_ENABLED", default=True)
ATLAS_DATA_PATH = env("ATLAS_DATA_PATH", default=str(BASE_DIR / "atlas-data.json"))
ATLAS_CACHE_TTL = env.int("ATLAS_CACHE_TTL", default=3600)
ATLAS_REAL_SAMPLES = env.bool("ATLAS_REAL_SAMPLES", default=True)
ATLAS_METADATA: dict = {}"""

CHECK_JOURNEYS = "uv run python scripts/check_journeys.py"
FEATURES = "docs/product/FEATURES.md"

MODULES: tuple[Module, ...] = (
    Module(
        name="journeys",
        summary="Feature list, user journeys and the /admin/journeys/ "
        "staff pages, with the JOURNEYS gate.",
        versions=("1.14.0",),
        paths=(
            "journeys",
            "scripts/check_journeys.py",
            "docs/product/README.md",
            ".agents/skills/journey-sync",
        ),
        seeds=(
            Seed(FEATURES, FEATURES_SEED, (FEATURES,)),
            Seed(
                "docs/product/journeys/J-001-sign-in.md",
                JOURNEY_SEED,
                ("docs/product/journeys/*.md", FEATURES),
            ),
        ),
        docs=("journeys/README.md", "docs/product/README.md"),
        steps=(
            UNFOLD_PREREQ,
            PYYAML,
            _app_step("journeys", "user journeys (feature and e2e traceability)"),
            Step(
                "Add the switch (the pages read docs/ from disk; keep them off in prod)",
                "settings: common, then prod",
                'JOURNEYS_ENABLED = env.bool("JOURNEYS_ENABLED", default=True)\n'
                "# prod settings:\n"
                'JOURNEYS_ENABLED = env.bool("JOURNEYS_ENABLED", default=False)',
            ),
            _urls_step(
                "from journeys.views import journey_detail_view, journeys_admin_view",
                'path("admin/journeys/", journeys_admin_view, name="journeys_admin"),\n'
                'path("admin/journeys/<str:journey_id>/", journey_detail_view, '
                'name="journey_detail"),',
            ),
            _sidebar_step("User Journeys", "route", "journeys_admin"),
            _recipe_step(
                "Check that FEATURES.md, journey specs and Playwright tags agree",
                "check-journeys",
                CHECK_JOURNEYS,
            ),
            _gate_step("JOURNEYS", CHECK_JOURNEYS),
            _packages_step("journeys"),
            Step(
                "Point the pages at the frontend when it is not at ../frontend",
                ".env",
                "JOURNEYS_E2E_DIR=../web/e2e\n"
                "JOURNEYS_E2E_REPORT=../web/test-results/journeys.json",
            ),
            Step(
                "journeys/tests/ needs a staff_user fixture and journey J-001",
                "conftest.py (skip when it already has staff_user)",
                STAFF_FIXTURE,
            ),
            Step(
                "Verify",
                "shell",
                f"{CHECK_JOURNEYS}\nuv run python manage.py check\n"
                "uv run pytest journeys -q\n"
                "# then open /admin/journeys/ as a staff user",
            ),
        ),
    ),
    Module(
        name="tickets",
        summary="File-based tickets for worker models (docs/tickets/), the "
        "TICKETS gate and the planner and worker skills.",
        versions=("1.14.0",),
        paths=(
            "scripts/tickets.py",
            "docs/tickets/README.md",
            "docs/tickets/TEMPLATE.md",
            "docs/AGENT_HANDOFF.md",
            ".agents/skills/ticket-planner",
            ".agents/skills/ticket-worker",
        ),
        docs=("docs/tickets/README.md", "docs/AGENT_HANDOFF.md"),
        steps=(
            PYYAML,
            _recipe_step(
                "Ticket queue: just tickets check | next --tier small | "
                "show T-001 | claim T-001",
                "tickets *args",
                "uv run python scripts/tickets.py {{ args }}",
            ),
            _gate_step("TICKETS", "uv run python scripts/tickets.py check"),
            Step(
                "Optional: describe the work modes for agents",
                "AGENTS.md (paste and adapt; this script never writes it)",
                source=("AGENTS.md", "## 14 Work modes and handoff"),
            ),
            Step(
                "Verify",
                "shell",
                "uv run python scripts/tickets.py check\n"
                "uv run python scripts/tickets.py next --tier small",
            ),
        ),
    ),
    Module(
        name="testing-policy",
        summary="Lean testing policy: TTSR rules for oh-my-pi plus the "
        "AGENTS.md text to paste.",
        versions=("1.13.0", "1.14.0"),
        paths=(
            ".omp/rules/ttsr-test-new-file.md",
            ".omp/rules/ttsr-test-assertions.md",
        ),
        steps=(
            Step(
                "Paste the policy into the target AGENTS.md and adapt the paths",
                "AGENTS.md (this script never writes it)",
                source=("AGENTS.md", "### Testing policy"),
            ),
            Step(
                "Remove a coverage floor from the default pytest options",
                "pyproject.toml [tool.pytest.ini_options] addopts",
                '# delete "--cov-fail-under=NN" (and "--cov" for fast default runs)',
            ),
            Step(
                "The rules run only under the oh-my-pi harness",
                "note",
                "Other harnesses read the AGENTS.md text. Keep both in sync.",
            ),
        ),
    ),
    Module(
        name="atlas",
        summary="Codebase Atlas: interactive architecture map at /admin/atlas/ "
        "and the system-design-atlas skill.",
        versions=("1.11.0", "1.12.0"),
        paths=("atlas", ".agents/skills/system-design-atlas"),
        docs=("docs/ATLAS_ADOPTION_PROMPT.md",),
        steps=(
            UNFOLD_PREREQ,
            _app_step("atlas", "codebase atlas (interactive architecture map)"),
            Step("Add the settings block", "settings", ATLAS_SETTINGS),
            Step(
                "Load the Unfold settings module if it is separate",
                "end of the settings module",
                "from .unfold import UNFOLD  # noqa: F401 (re-exported into settings)",
            ),
            _urls_step(
                "from atlas.views import atlas_admin_view, atlas_data_view, "
                "atlas_regenerate_view",
                'path("admin/atlas/data.json", atlas_data_view, name="atlas_data"),\n'
                'path("admin/atlas/regenerate/", atlas_regenerate_view, '
                'name="atlas_regenerate"),\n'
                'path("admin/atlas/", atlas_admin_view, name="atlas_admin"),',
            ),
            _sidebar_step("Codebase Atlas", "map", "atlas_admin"),
            Step("Ignore the generated data file", ".gitignore", "atlas-data.json"),
            _recipe_step(
                "Regenerate the codebase atlas data file",
                "update-architecture",
                "uv run python manage.py atlas",
            ),
            _packages_step("atlas"),
            Step(
                "Check the lazy imports",
                "atlas/services/introspect.py, atlas/services/samples.py",
                "introspect.py reads the NinjaAPI from api.urls.api; change the "
                "import if yours lives elsewhere.\nsamples.py reads "
                "core.audit.models.AuditLog and returns no samples without it.",
            ),
            Step(
                "Follow steps 4 to 6 (dashboard, admin index, verify)",
                "docs/ATLAS_ADOPTION_PROMPT.md",
                "uv run python manage.py atlas\n"
                "uv run python manage.py collectstatic --noinput\n"
                "# then open /admin/atlas/ as a staff user",
            ),
        ),
    ),
)


def get_module(name: str) -> Module:
    for module in MODULES:
        if module.name == name:
            return module
    names = ", ".join(m.name for m in MODULES)
    raise AdoptError(f"unknown module {name!r}; choose one of: {names}")


# Files


def _matches(rel: PurePosixPath, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(part, p) for part in rel.parts for p in patterns)


def module_files(module: Module) -> list[str]:
    """List the files of ``module`` in this repo, relative and sorted."""
    files: list[str] = []
    for entry in module.paths:
        src = REPO_ROOT / entry
        if src.is_file():
            candidates = [src]
        elif src.is_dir():
            candidates = sorted(p for p in src.rglob("*") if not p.is_dir())
        else:
            raise AdoptError(f"manifest path {entry} is missing from {REPO_ROOT}")
        for path in candidates:
            rel = PurePosixPath(path.relative_to(REPO_ROOT).as_posix())
            if _matches(rel, SKIP_NAMES):
                continue
            if _matches(rel, SECRET_PATTERNS):
                raise AdoptError(f"refusing to copy {rel}: it matches a secret pattern")
            if path.is_symlink():
                raise AdoptError(f"refusing to copy {rel}: it is a symlink")
            files.append(str(rel))
    return files


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_state(target: Path, rel: str) -> str:
    """Return ``missing``, ``same`` or ``differs`` for one module file."""
    dest = target / rel
    if not dest.exists():
        return "missing"
    if dest.is_file() and _sha256(dest) == _sha256(REPO_ROOT / rel):
        return "same"
    return "differs"


def seed_blocker(target: Path, seed: Seed) -> str | None:
    """Return the target path that blocks ``seed``, or None to write it."""
    for pattern in seed.unless:
        if any(target.glob(pattern)):
            return pattern
    return None


def _safe_dest(target: Path, rel: str) -> Path:
    dest = target / rel
    parent = dest.parent.resolve()
    if parent != target and target not in parent.parents:
        raise AdoptError(f"refusing to write {rel}: it resolves outside the target")
    if dest.is_symlink():
        raise AdoptError(f"refusing to write {rel}: it is a symlink in the target")
    return dest


# Git, target and state


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )


def boilerplate_version() -> str:
    return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def boilerplate_commit() -> str:
    result = _git(REPO_ROOT, "rev-parse", "--short", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def resolve_target(raw: str, *, need_git: bool) -> Path:
    """Validate ``--target``: a Django project, not this repo, maybe in git."""
    target = Path(raw).expanduser().resolve()
    if not target.is_dir():
        raise AdoptError(f"{target} is not a directory")
    if target == REPO_ROOT or REPO_ROOT in target.parents:
        raise AdoptError(f"{target} is this boilerplate; pass the other backend")
    if not (target / "manage.py").is_file():
        raise AdoptError(f"{target} has no manage.py; pass the Django project root")
    if need_git:
        top = _git(target, "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            raise AdoptError(
                f"{target} is not in a git work tree; commit it first so git "
                "can undo the copy"
            )
        if Path(top.stdout.strip()).resolve() == REPO_ROOT:
            raise AdoptError(f"{target} is in this boilerplate's git tree")
    return target


def dirty_paths(target: Path, rels: list[str]) -> list[str]:
    """Return the paths in ``rels`` that are modified, staged or untracked."""
    if not rels:
        return []
    result = _git(target, "status", "--porcelain", "--untracked-files=all", "--", *rels)
    if result.returncode != 0:
        raise AdoptError(f"git status failed in {target}: {result.stderr.strip()}")
    dirty = {line[3:].strip().strip('"') for line in result.stdout.splitlines()}
    prefix = _git(target, "rev-parse", "--show-prefix").stdout.strip()
    return [rel for rel in rels if rel in dirty or f"{prefix}{rel}" in dirty]


def read_state(target: Path) -> dict[str, Any]:
    path = target / STATE_FILE
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise AdoptError(f"{path} is not valid TOML: {exc}") from exc


def _toml_str(value: object) -> str:
    return json.dumps(str(value))  # a JSON string is a valid TOML basic string


def write_state(target: Path, state: dict[str, Any]) -> None:
    lines = [
        "# Written by django-ninja-boilerplate scripts/adopt.py. Commit this file.",
        "# boilerplate_version: the boilerplate VERSION at the last apply.",
        "# [modules.<name>]: one table per adopted module.",
        "",
    ]
    for key in ("boilerplate_version", "boilerplate_commit", "updated"):
        if key in state:
            lines.append(f"{key} = {_toml_str(state[key])}")
    for name, record in sorted(state.get("modules", {}).items()):
        lines += ["", f"[modules.{name}]"]
        lines += [f"{k} = {_toml_str(v)}" for k, v in sorted(record.items())]
    dest = _safe_dest(target, STATE_FILE)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Changelog and markdown

HEADING = re.compile(r"^## \[(?P<version>[^\]]+)\](?P<rest>.*)$")


def version_key(version: str) -> tuple[int, ...]:
    if version.strip().lower() == "unreleased":
        return (sys.maxsize,)
    numbers = re.findall(r"\d+", version)
    if not numbers:
        raise AdoptError(f"cannot read version {version!r}; use x.y.z")
    return tuple(int(n) for n in numbers[:3])


def changelog_sections() -> list[tuple[str, str, str]]:
    """Return (version, heading, body) for each ``## [x.y.z]`` section."""
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    sections: list[tuple[str, str, list[str]]] = []
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            sections.append((match["version"], line, []))
        elif sections:
            sections[-1][2].append(line)
    return [(v, h, "\n".join(body).strip()) for v, h, body in sections]


def markdown_section(rel: str, heading: str) -> str:
    """Return ``heading`` and its body from a markdown file in this repo."""
    lines = (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    out: list[str] = []
    for line in lines:
        if out:
            depth = len(line) - len(line.lstrip("#"))
            if 0 < depth <= level and line[depth : depth + 1] == " ":
                break
            out.append(line)
        elif line.strip() == heading:
            out.append(line)
    if not out:
        raise AdoptError(f"heading {heading!r} not found in {rel}")
    return "\n".join(out).strip()


def print_wiring(module: Module, target: Path) -> None:
    print(f"\nWiring for {module.name}. Apply these by hand in {target}:")
    for number, step in enumerate(module.steps, start=1):
        print(f"\n{number:>2}. {step.title}  [{step.where}]")
        snippet = markdown_section(*step.source) if step.source else step.snippet
        for line in snippet.splitlines():
            print(f"      {line}" if line else "")
    if module.docs:
        print(f"\nRead in the boilerplate: {', '.join(module.docs)}")
    print(
        "\nThen run the target's own gates (tests, lint, type check) and commit "
        "this module on its own branch."
    )


# Commands


def cmd_list(_: argparse.Namespace) -> int:
    print(f"Boilerplate {boilerplate_version()} at {REPO_ROOT}\n")
    print(f"{'MODULE':<16}{'SINCE':<12}{'FILES':>6}  DESCRIPTION")
    for module in MODULES:
        count = len(module_files(module))
        print(f"{module.name:<16}{module.versions[0]:<12}{count:>6}  {module.summary}")
    print(f"\nNext: {SCRIPT} status --target ../my-api")
    return 0


def _module_status(target: Path, module: Module, record: dict[str, Any] | None) -> str:
    files = module_files(module)
    states = [file_state(target, rel) for rel in files]
    same, missing = states.count("same"), states.count("missing")
    present = len(files) - missing
    if record is None:
        detail = f"{present}/{len(files)} files present" if present else ""
        return f"{'not adopted':<14}{detail}".rstrip()
    if same == len(files):
        label, detail = "adopted", f"{same}/{len(files)} same"
    else:
        label = "files differ"
        detail = f"{same} same, {states.count('differs')} differ, {missing} missing"
    recorded = str(record.get("version", "?"))
    if version_key(module.versions[-1]) > version_key(recorded):
        detail += f"; boilerplate has {module.versions[-1]} changes"
    return f"{label:<14}{detail} (recorded {recorded})"


def cmd_status(args: argparse.Namespace) -> int:
    target = resolve_target(args.target, need_git=False)
    state = read_state(target)
    records: dict[str, Any] = state.get("modules", {})
    recorded = state.get("boilerplate_version")
    print(f"Boilerplate  {boilerplate_version()} ({boilerplate_commit()}) {REPO_ROOT}")
    print(f"Target       {target}")
    if recorded:
        print(f"Recorded     {recorded} in {STATE_FILE}")
    else:
        print(f"Recorded     none ({STATE_FILE} absent: never adopted)")
    print(f"\n{'MODULE':<16}{'STATE':<14}DETAIL")
    for module in MODULES:
        line = _module_status(target, module, records.get(module.name))
        print(f"{module.name:<16}{line}")

    since = args.since or recorded
    sections = changelog_sections()
    if not since:
        print("\nChangelog versions (pass --since x.y.z to print the sections):")
        for _version, heading, _body in sections:
            print(f"  {heading[3:]}")
        return 0
    newer = [s for s in sections if version_key(s[0]) > version_key(str(since))]
    print(f"\nChangelog sections newer than {since}:")
    if not newer:
        print("  none")
    for _version, heading, body in newer:
        print(f"\n{heading}\n\n{body}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    module = get_module(args.module)
    target = resolve_target(args.target, need_git=False)
    files = module_files(module)
    print(f"{module.name}: {len(files)} files, {len(module.seeds)} seed files")
    differing: list[str] = []
    for rel in files:
        state = file_state(target, rel)
        print(f"  {state:<8} {rel}")
        if state == "differs":
            differing.append(rel)
    for seed in module.seeds:
        blocker = seed_blocker(target, seed)
        action = f"skip, target has {blocker}" if blocker else "create"
        print(f"  {'seed':<8} {seed.path} ({action})")
    if args.patch:
        for rel in differing:
            _print_patch(target, rel)
    elif differing:
        print(
            f"\nShow the changes: {SCRIPT} diff {module.name} "
            f"--target {args.target} --patch"
        )
    return 0


def _print_patch(target: Path, rel: str) -> None:
    try:
        ours = (target / rel).read_text(encoding="utf-8").splitlines(keepends=True)
        theirs = (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines(keepends=True)
    except (UnicodeDecodeError, IsADirectoryError):
        print(f"\n{rel}: binary or not a file, no patch")
        return
    print()
    sys.stdout.writelines(
        difflib.unified_diff(ours, theirs, f"target/{rel}", f"boilerplate/{rel}")
    )


def cmd_apply(args: argparse.Namespace) -> int:
    module = get_module(args.module)
    target = resolve_target(args.target, need_git=True)
    files = module_files(module)
    plan = {rel: file_state(target, rel) for rel in files}
    copy = [rel for rel, state in plan.items() if state == "missing"]
    differ = [rel for rel, state in plan.items() if state == "differs"]
    seeds = [seed for seed in module.seeds if seed_blocker(target, seed) is None]

    if differ and not args.force:
        print(f"Refusing to apply {module.name}: {len(differ)} file(s) differ:")
        for rel in differ:
            print(f"  differs  {rel}")
        print(
            f"\nReview: {SCRIPT} diff {module.name} --target {args.target} --patch\n"
            "Keep your version, or commit your work and rerun with --force "
            "(git restores your version)."
        )
        return 1
    dirty = dirty_paths(target, differ)
    if dirty:
        print("Refusing to overwrite files with uncommitted changes:")
        for rel in dirty:
            print(f"  dirty    {rel}")
        print("\nCommit or stash them first, so git can undo the overwrite.")
        return 1

    verb = "Would" if args.dry_run else "Will"
    same = len(files) - len(copy) - len(differ)
    print(f"{module.name} -> {target}")
    print(
        f"{verb} copy {len(copy)}, overwrite {len(differ)}, seed {len(seeds)}; "
        f"{same} already the same."
    )
    for label, rels in (("copy", copy), ("overwrite", differ)):
        for rel in rels:
            print(f"  {label:<9} {rel}")
    for seed in seeds:
        print(f"  {'seed':<9} {seed.path}")

    if not args.dry_run:
        for rel in copy + differ:
            dest = _safe_dest(target, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / rel, dest)
            shutil.copymode(REPO_ROOT / rel, dest)
        for seed in seeds:
            dest = _safe_dest(target, seed.path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(seed.content, encoding="utf-8")
        _record(target, module)
        print(f"Recorded {module.name} {module.versions[-1]} in {STATE_FILE}.")
    print_wiring(module, target)
    return 0


def _record(target: Path, module: Module) -> None:
    state = read_state(target)
    today = datetime.now(UTC).date().isoformat()
    version, commit = boilerplate_version(), boilerplate_commit()
    state.update(boilerplate_version=version, boilerplate_commit=commit, updated=today)
    state.setdefault("modules", {})[module.name] = {
        "version": module.versions[-1],
        "boilerplate_version": version,
        "adopted": today,
    }
    write_state(target, state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show and copy portable boilerplate modules into another "
        "Django backend. See docs/ADOPTING_UPDATES.md."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="list the portable modules").set_defaults(func=cmd_list)

    status = sub.add_parser("status", help="show adoption state and new changes")
    status.add_argument("--target", required=True, help="the other backend")
    status.add_argument("--since", help="print changelog sections newer than this")
    status.set_defaults(func=cmd_status)

    diff = sub.add_parser("diff", help="compare one module with the target")
    diff.add_argument("module")
    diff.add_argument("--target", required=True, help="the other backend")
    diff.add_argument("--patch", action="store_true", help="print unified diffs")
    diff.set_defaults(func=cmd_diff)

    apply = sub.add_parser("apply", help="copy one module and print its wiring")
    apply.add_argument("module")
    apply.add_argument("--target", required=True, help="the other backend")
    apply.add_argument("--dry-run", action="store_true", help="write nothing")
    apply.add_argument(
        "--force", action="store_true", help="overwrite committed differing files"
    )
    apply.set_defaults(func=cmd_apply)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except AdoptError as exc:
        print(f"adopt: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
