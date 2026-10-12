"""Helpers for scripts/gauntlet.py gates: test environment and change detection."""

from __future__ import annotations

import subprocess

# Test settings without the developer's .env (api/settings/common.py reads it
# unless DJANGO_READ_DOT_ENV=0), so gate results match on every machine.
TEST_ENV = {"DJANGO_SETTINGS_MODULE": "api.settings.test", "DJANGO_READ_DOT_ENV": "0"}

# Paths whose changes can break a generator: the generators themselves and
# the schema base class every generated schema inherits.
GENERATOR_PATHS = ("core/management/commands/", "core/schemas/base_schema.py")
BASE_REF = "origin/main"


def _git_names(*args: str) -> list[str]:
    """Return the file names a git command prints, or [] when git fails."""
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return result.stdout.splitlines() if result.returncode == 0 else []


def changed_files() -> set[str]:
    """Files changed in the working tree, the index, or the branch.

    The branch part compares HEAD with its merge base on ``origin/main``;
    it is empty when that ref does not exist.
    """
    names = set(_git_names("diff", "--name-only", "HEAD"))
    names |= set(_git_names("ls-files", "--others", "--exclude-standard"))
    base = _git_names("merge-base", "HEAD", BASE_REF)
    if base:
        names |= set(_git_names("diff", "--name-only", base[0], "HEAD"))
    return names


def generator_changes() -> list[str]:
    """Changed files under GENERATOR_PATHS, sorted."""
    return sorted(name for name in changed_files() if name.startswith(GENERATOR_PATHS))
