#!/usr/bin/env python3
"""Bump the project version and cut a release.

Usage:
    python scripts/release.py           # next patch version
    python scripts/release.py 1.11.0    # explicit version

The script bumps the version in pyproject.toml, api/settings/common.py
(APP_VERSION default), the Makefile banner, and the VERSION file; retitles
the CHANGELOG [Unreleased] section to the new version and inserts the new
compare link; syncs uv.lock; then commits, tags vX.Y.Z, and pushes.

Run with --dry-run to preview the file changes without committing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "mattjaikaran/django-ninja-boilerplate"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

    pyproject_path = ROOT / "pyproject.toml"
    pyproject = pyproject_path.read_text()
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    if not match:
        sys.exit("error: version not found in pyproject.toml")
    current = match.group(1)

    if args:
        version = args[0]
    else:
        major, minor, patch = (int(part) for part in current.split("."))
        version = f"{major}.{minor}.{patch + 1}"

    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit(f"error: invalid version '{version}' (expected semver)")
    if version == current:
        sys.exit(f"error: version '{version}' is already current")

    print(f"Bumping {current} -> {version}" + (" (dry run)" if dry_run else ""))

    # Version strings
    pyproject = pyproject.replace(f'version = "{current}"', f'version = "{version}"')
    common_path = ROOT / "api" / "settings" / "common.py"
    common = common_path.read_text().replace(
        f'default="{current}"', f'default="{version}"'
    )
    makefile_path = ROOT / "Makefile"
    makefile = makefile_path.read_text().replace(f"v{current}", f"v{version}")
    version_file = ROOT / "VERSION"

    if dry_run:
        print(f"  pyproject.toml: {current} -> {version}")
        print(f"  api/settings/common.py: APP_VERSION default={version}")
        print(f"  Makefile banner: v{version}")
        print(f"  VERSION file: {version}")
    else:
        pyproject_path.write_text(pyproject)
        common_path.write_text(common)
        makefile_path.write_text(makefile)
        version_file.write_text(version + "\n")
        run(["uv", "lock"])

    # CHANGELOG: retitle Unreleased, refresh the HEAD link, and insert the
    # new version's compare link above the previous version's (which stays).
    changelog_path = ROOT / "CHANGELOG.md"
    changelog = changelog_path.read_text()
    today = datetime.now(UTC).date().isoformat()
    changelog = changelog.replace("## [Unreleased]", f"## [{version}] - {today}", 1)
    changelog = re.sub(
        r"^\[Unreleased\]: .*$",
        f"[Unreleased]: https://github.com/{REPO}/compare/v{version}...HEAD",
        changelog,
        count=1,
        flags=re.MULTILINE,
    )
    new_link = f"[{version}]: https://github.com/{REPO}/compare/v{current}...v{version}"
    changelog = re.sub(
        rf"^(\[{re.escape(current)}\]: .*)$",
        new_link + r"\n\1",
        changelog,
        count=1,
        flags=re.MULTILINE,
    )
    if dry_run:
        print(f"  CHANGELOG: [Unreleased] -> [{version}] - {today}")
        print(f"  CHANGELOG: inserted compare link {new_link}")
    else:
        changelog_path.write_text(changelog)
        run(
            [
                "git",
                "add",
                "pyproject.toml",
                "api/settings/common.py",
                "Makefile",
                "VERSION",
                "uv.lock",
                "CHANGELOG.md",
            ]
        )
        run(["git", "commit", "-m", f"chore(release): Bump version to {version}"])
        run(["git", "tag", f"v{version}"])
        run(["git", "push", "origin", "main", "--tags"])
        print(f"Released v{version}")


if __name__ == "__main__":
    main()
