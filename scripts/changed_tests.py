#!/usr/bin/env python3
"""Print the pytest targets for the files changed since HEAD.

`just test` uses this for its fast default run. A changed test file maps to
itself, a changed ``conftest.py`` to its directory, and any other changed
Python file in an app to ``<app>/tests``. Only paths under
``[tool.pytest.ini_options] testpaths`` count: apps outside it are not
installed in the test settings.

Prints nothing, so the caller runs the whole suite, when any change cannot be
mapped: a deleted Python file, a Python file with no test target inside
testpaths (settings, ``api/``, ``scripts/``, a root ``conftest.py``), or a
change to ``pyproject.toml`` or ``uv.lock``. Other non-Python files are
ignored.

Usage:
    python scripts/changed_tests.py
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


#: Changes to these files can affect every test.
WHOLE_SUITE_FILES = {"pyproject.toml", "uv.lock"}


def changed_files() -> list[str]:
    """Staged, unstaged, deleted and untracked files, relative to the root."""
    names = _git("diff", "--name-only", "HEAD")
    names += _git("ls-files", "--others", "--exclude-standard")
    return sorted(set(names))


def _within(path: PurePosixPath, roots: list[PurePosixPath]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def targets(files: list[str], testpaths: list[str]) -> list[str]:
    """Map changed files to pytest targets; empty means run every test."""
    roots = [PurePosixPath(path) for path in testpaths]
    found: set[PurePosixPath] = set()
    for name in files:
        path = PurePosixPath(name)
        if name in WHOLE_SUITE_FILES:
            return []
        if path.suffix != ".py":
            continue
        if path.name.startswith("test_") or path.name == "conftest.py":
            target = path if path.name.startswith("test_") else path.parent
        else:
            target = PurePosixPath(path.parts[0]) / "tests"
        mapped = _within(target, roots) and (PROJECT_ROOT / target).exists()
        if not mapped or not (PROJECT_ROOT / path).is_file():
            return []
        found.add(target)
    # Drop a target when a directory that contains it is already a target.
    return sorted(str(t) for t in found if not any(p in found for p in t.parents))


def main() -> int:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text("utf-8"))
    testpaths = pyproject["tool"]["pytest"]["ini_options"]["testpaths"]
    print(" ".join(targets(changed_files(), testpaths)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
