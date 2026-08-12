#!/usr/bin/env python3
"""Dependency gate — fail when pyproject.toml changes without a DEPENDENCIES.md entry.

Anti-slop constraint: a dependency-manifest change must ship with an entry in
DEPENDENCIES.md so new dependencies get reviewed instead of silently merged.

The check compares the working tree against HEAD. It passes when pyproject.toml
is unchanged, or when DEPENDENCIES.md changed alongside it. It fails when
pyproject.toml changed but DEPENDENCIES.md did not.

Usage:
    python scripts/check_dependencies.py        # check working tree vs HEAD
    python scripts/check_dependencies.py --all  # full-project scan (same)

Exit: 0 = pass, 1 = pyproject.toml changed but DEPENDENCIES.md did not
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_TOML = Path("pyproject.toml")
DEPENDENCIES_MD = Path("DEPENDENCIES.md")


def _read_head(repo_root: Path, rel_path: Path) -> str | None:
    """Return the file content at HEAD, or None when absent from HEAD."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path.as_posix()}"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def file_changed(repo_root: Path, rel_path: Path) -> bool:
    """Return True when the working-tree file differs from HEAD.

    Detects new (untracked), modified, and deleted files by comparing the
    on-disk content to the committed blob.
    """
    disk_path = repo_root / rel_path
    on_disk = disk_path.read_text(encoding="utf-8") if disk_path.exists() else None
    return on_disk != _read_head(repo_root, rel_path)


def evaluate(pyproject_changed: bool, dependencies_changed: bool) -> tuple[bool, str]:
    """Apply the dependency-gate rule. Return (passed, message)."""
    if not pyproject_changed:
        return True, "pyproject.toml unchanged"
    if dependencies_changed:
        return True, "pyproject.toml changed and DEPENDENCIES.md updated"
    return False, (
        "pyproject.toml changed but DEPENDENCIES.md has no matching entry; "
        "add the dependency to DEPENDENCIES.md and stage it with pyproject.toml"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail when pyproject.toml changes without a DEPENDENCIES.md entry"
    )
    parser.add_argument("--all", action="store_true", help="Check the full project")
    parser.parse_args(argv)

    pyproject_changed = file_changed(PROJECT_ROOT, PYPROJECT_TOML)
    dependencies_changed = file_changed(PROJECT_ROOT, DEPENDENCIES_MD)

    passed, message = evaluate(pyproject_changed, dependencies_changed)
    if passed:
        print(f"  Check passed: {message}")
    else:
        print(f"  FAIL: {message}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
