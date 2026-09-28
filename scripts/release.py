#!/usr/bin/env python3
"""Bump the project version and cut a release.

Usage:
    python scripts/release.py --dry-run          # preview the next patch
    python scripts/release.py 1.12.0 --dry-run   # preview an explicit version
    python scripts/release.py 1.12.0             # commit and tag locally
    python scripts/release.py 1.12.0 --push      # also push main and tags

The script bumps the version in pyproject.toml, api/settings/common.py
(APP_VERSION default), the justfile banner, and the VERSION file; retitles
the CHANGELOG [Unreleased] section to the new version and inserts the new
compare link; syncs uv.lock; then commits and tags vX.Y.Z. It pushes only
with --push. Unknown arguments exit with an error before any file or git
change.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "mattjaikaran/django-ninja-boilerplate"


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bump the version, then commit and tag the release."
    )
    parser.add_argument(
        "version",
        nargs="?",
        help="Explicit X.Y.Z version. Defaults to the next patch version.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the changes without writing files or running git.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push main and tags to origin after the commit and tag.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    options = parse_args(argv)
    dry_run = options.dry_run
    pyproject_path = ROOT / "pyproject.toml"
    pyproject = pyproject_path.read_text()
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    if not match:
        sys.exit("error: version not found in pyproject.toml")
    current = match.group(1)

    if options.version:
        version = options.version
    else:
        major, minor, patch = (int(part) for part in current.split("."))
        version = f"{major}.{minor}.{patch + 1}"

    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit(f"error: invalid version '{version}' (expected semver)")
    if version == current:
        sys.exit(f"error: version '{version}' is already current")

    # The release commit stages only the version files, so anything else left
    # in the tree would be silently excluded from the tagged commit. Refuse to
    # release from a dirty tree instead.
    if not dry_run:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if status:
            sys.exit(
                "error: the working tree has uncommitted changes; commit or "
                f"stash them first:\n{status}"
            )

    print(f"Bumping {current} -> {version}" + (" (dry run)" if dry_run else ""))

    # Version strings
    pyproject = pyproject.replace(f'version = "{current}"', f'version = "{version}"')
    common_path = ROOT / "api" / "settings" / "common.py"
    common = common_path.read_text().replace(
        f'default="{current}"', f'default="{version}"'
    )
    justfile_path = ROOT / "justfile"
    justfile = justfile_path.read_text().replace(f"v{current}", f"v{version}")
    version_file = ROOT / "VERSION"

    if dry_run:
        print(f"  pyproject.toml: {current} -> {version}")
        print(f"  api/settings/common.py: APP_VERSION default={version}")
        print(f"  justfile banner: v{version}")
        print(f"  VERSION file: {version}")
    else:
        pyproject_path.write_text(pyproject)
        common_path.write_text(common)
        justfile_path.write_text(justfile)
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
        return
    changelog_path.write_text(changelog)
    # uv.lock is tracked (reproducible installs), so bump it too.
    run(
        [
            "git",
            "add",
            "pyproject.toml",
            "api/settings/common.py",
            "justfile",
            "VERSION",
            "CHANGELOG.md",
            "uv.lock",
        ]
    )
    run(["git", "commit", "-m", f"chore(release): Bump version to {version}"])
    run(["git", "tag", f"v{version}"])
    if not options.push:
        print(f"Tagged v{version} locally. Push with: git push origin main --tags")
        return
    run(["git", "push", "origin", "main", "--tags"])
    print(f"Released v{version}")


if __name__ == "__main__":
    main()
