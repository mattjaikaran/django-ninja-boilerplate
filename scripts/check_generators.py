#!/usr/bin/env python3
"""GENERATORS gate: every feature generator produces a working, wired app.

Creates a throwaway ``git worktree`` of HEAD in a temp dir, copies the main
tree's uncommitted changes into it (so the gate checks the working tree),
then runs each ``manage.py generate_feature`` generator plus
``startapp_extended`` there. It then runs ``manage.py check``,
``makemigrations --check --dry-run``, ``ruff check``, ``ruff format --check``
and ``pytest`` on the generated files. The main tree is never modified.

Contract tests (``tests/contract``) are not run: route-classification tests
fail on purpose when new routes appear.

Usage:
    python scripts/check_generators.py                  # every generator
    python scripts/check_generators.py --only team,chat # a subset
    python scripts/check_generators.py --keep           # keep the worktree
    python scripts/check_generators.py --inject-failure # prove the gate fails

Exit: 0 = every step passed, 1 = at least one step failed
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAIL_LINES = 20
STEP_TIMEOUT = 600
WIRING_FILES = ("api/urls.py", "api/settings/common.py")
INJECTED_ERROR = "\n\ndef injected_failure(:\n"


@dataclass(frozen=True)
class Generator:
    """One generator run: its name, manage.py arguments and target app."""

    name: str
    argv: tuple[str, ...]
    app: str
    wired: bool = True


GENERATORS: tuple[Generator, ...] = (
    Generator(
        "api_endpoint",
        ("generate_feature", "api_endpoint", "--app-name", "widgets"),
        "widgets",
    ),
    Generator("team", ("generate_feature", "team"), "team"),
    Generator("rbac", ("generate_feature", "rbac"), "rbac"),
    Generator("payments", ("generate_feature", "payments"), "payments"),
    Generator(
        "notification",
        ("generate_feature", "notification", "--app-name", "notifs"),
        "notifs",
    ),
    Generator("chat", ("generate_feature", "chat"), "chat"),
    Generator(
        "organization",
        ("generate_feature", "organization", "--app-name", "orgs"),
        "orgs",
    ),
    Generator("graphql", ("generate_feature", "graphql", "--app-name", "core"), "core"),
    Generator("redis", ("generate_feature", "redis", "--app-name", "rcache"), "rcache"),
    Generator(
        "startapp_extended", ("startapp_extended", "gadget"), "gadget", wired=False
    ),
)
GENERATOR_NAMES = tuple(gen.name for gen in GENERATORS)


def _git(*args: str, cwd: Path) -> str:
    """Run git and return stdout. Raise on failure."""
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout


def _porcelain(cwd: Path) -> list[tuple[str, str]]:
    """Return ``(status, path)`` pairs from ``git status``, one per file.

    A rename yields the new path with its status and the old path as ``D``.
    Untracked files are listed one by one; ignored files are left out.
    """
    out = _git("status", "--porcelain", "-z", "--untracked-files=all", cwd=cwd)
    entries = out.split("\0")
    pairs: list[tuple[str, str]] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status, path = entry[:2], entry[3:]
        pairs.append((status, path))
        if "R" in status or "C" in status:
            old = entries[index]
            index += 1
            if "R" in status:
                pairs.append(("D ", old))
    return pairs


def _copy_working_changes(src: Path, dest: Path) -> int:
    """Mirror the uncommitted changes of ``src`` into ``dest``. Return the count."""
    count = 0
    for _status, rel in _porcelain(src):
        source, target = src / rel, dest / rel
        if source.is_file() or source.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)
        elif target.is_file() or target.is_symlink():
            target.unlink()
        else:
            continue
        count += 1
    return count


def _env() -> dict[str, str]:
    """Return the child environment: test settings, no CI or TEST_DB."""
    env = {k: v for k, v in os.environ.items() if k not in {"CI", "TEST_DB"}}
    env["DJANGO_SETTINGS_MODULE"] = "api.settings.test"
    return env


def _run_step(name: str, argv: list[str], cwd: Path) -> bool:
    """Run one step, print ``OK|FAIL <name> (<s>s)`` and the tail on failure."""
    start = time.monotonic()
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=_env(),
            capture_output=True,
            check=False,
            timeout=STEP_TIMEOUT,
            text=True,
        )
        output = result.stdout + result.stderr
        ok = result.returncode == 0
    except subprocess.TimeoutExpired as exc:
        output = f"timed out after {exc.timeout}s"
        ok = False
    elapsed = time.monotonic() - start
    print(f"{'OK' if ok else 'FAIL'} {name} ({elapsed:.1f}s)", flush=True)
    if not ok:
        for line in output.rstrip().splitlines()[-TAIL_LINES:]:
            print(f"    {line}")
    return ok


def _changed_files(cwd: Path) -> list[str]:
    """Return files changed since the baseline was staged, deletions excluded.

    The baseline is staged, so only the work-tree column (or ``??``) counts.
    """
    return sorted(rel for status, rel in _porcelain(cwd) if status[1] not in {" ", "D"})


def _pytest_targets(changed: list[str], selected: list[Generator]) -> list[str]:
    """Return the generated test files of the wired generators."""
    apps = {gen.app for gen in selected if gen.wired}
    return [
        rel
        for rel in changed
        if rel.split("/", 1)[0] in apps
        and "/tests/" in f"/{rel}"
        and Path(rel).name.startswith("test_")
        and rel.endswith(".py")
    ]


def _inject_failure(worktree: Path, changed: list[str], app: str) -> str:
    """Append a syntax error to the first generated module of ``app``."""
    candidates = [
        rel
        for rel in changed
        if rel.startswith(f"{app}/")
        and rel.endswith(".py")
        and Path(rel).name != "__init__.py"
    ]
    if not candidates:
        msg = f"no generated module in {app} to break"
        raise SystemExit(msg)
    target = candidates[0]
    with (worktree / target).open("a", encoding="utf-8") as handle:
        handle.write(INJECTED_ERROR)
    return target


def _run_checks(
    worktree: Path, selected: list[Generator], inject_failure: bool
) -> list[bool]:
    """Run every generator and every post-generation check in ``worktree``."""
    py = sys.executable
    results = [
        _run_step(gen.name, [py, "manage.py", *gen.argv], worktree) for gen in selected
    ]
    results.append(_run_step("check", [py, "manage.py", "check"], worktree))
    results.append(
        _run_step(
            "makemigrations",
            [py, "manage.py", "makemigrations", "--check", "--dry-run"],
            worktree,
        )
    )

    changed = _changed_files(worktree)
    if inject_failure:
        target = _inject_failure(worktree, changed, selected[0].app)
        print(f"INJECTED syntax error into {target}", flush=True)
    apps = {gen.app for gen in selected}
    lint_files = [
        rel
        for rel in changed
        if rel.endswith(".py") and (rel.split("/", 1)[0] in apps or rel in WIRING_FILES)
    ]
    for rel in WIRING_FILES:
        if rel not in lint_files:
            lint_files.append(rel)
    ruff = [py, "-m", "ruff"]
    results.append(
        _run_step("ruff-check", [*ruff, "check", "--no-fix", *lint_files], worktree)
    )
    results.append(
        _run_step("ruff-format", [*ruff, "format", "--check", *lint_files], worktree)
    )

    tests = _pytest_targets(changed, selected)
    if tests:
        argv = [py, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider"]
        results.append(_run_step("pytest", [*argv, "--no-header"], worktree))
    else:
        print("SKIP pytest (no generated tests)", flush=True)
    return results


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--keep", action="store_true", help="keep the worktree and print its path"
    )
    parser.add_argument(
        "--only",
        metavar="NAME[,NAME]",
        help=f"run a subset of generators: {', '.join(GENERATOR_NAMES)}",
    )
    parser.add_argument(
        "--inject-failure",
        action="store_true",
        help="debug: append a syntax error to a generated file before ruff",
    )
    return parser.parse_args(argv)


def _select(only: str | None) -> list[Generator]:
    if not only:
        return list(GENERATORS)
    names = [name.strip() for name in only.split(",") if name.strip()]
    unknown = sorted(set(names) - set(GENERATOR_NAMES))
    if unknown:
        msg = f"unknown generator(s): {', '.join(unknown)}"
        msg += f"; choose from {', '.join(GENERATOR_NAMES)}"
        raise SystemExit(msg)
    return [gen for gen in GENERATORS if gen.name in names]


def main(argv: list[str] | None = None) -> int:
    """Run the gate. Return the process exit code."""
    args = _parse_args(argv)
    selected = _select(args.only)
    start = time.monotonic()
    tmp = Path(tempfile.mkdtemp(prefix="check-generators-"))
    worktree = tmp / "tree"
    try:
        _git("worktree", "add", "--detach", str(worktree), "HEAD", cwd=ROOT)
        copied = _copy_working_changes(ROOT, worktree)
        _git("add", "-A", cwd=worktree)
        print(f"Worktree of HEAD + {copied} uncommitted file(s)", flush=True)
        results = _run_checks(worktree, selected, args.inject_failure)
    finally:
        if args.keep:
            print(f"Kept worktree: {worktree}")
        else:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["git", "worktree", "prune"], cwd=ROOT, capture_output=True, check=False
            )
            shutil.rmtree(tmp, ignore_errors=True)
    failed = results.count(False)
    total = time.monotonic() - start
    verdict = "FAIL" if failed else "OK"
    print(f"{verdict} generators: {failed} failed step(s) in {total:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
