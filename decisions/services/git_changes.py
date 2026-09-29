"""Read commits from git as ``triage_change`` state.

The state matches the ``code_review_triage`` benchmark: ``title``,
``description``, ``files``, ``additions``, and ``deletions``. Git runs with an
argument list, never a shell, and a revision must not start with ``-`` so it
cannot be read as an option.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from api.exceptions import ValidationError

#: Most changed paths kept per commit, so a huge commit stays a small state.
MAX_FILES = 40

#: Longest commit body kept, in characters.
MAX_DESCRIPTION = 2000


def _git(args: list[str], cwd: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
        )
    except FileNotFoundError as exc:
        raise ValidationError("git is not installed.") from exc
    except subprocess.CalledProcessError as exc:
        raise ValidationError(
            f"git {' '.join(args)} failed: {exc.stderr.strip()}"
        ) from exc
    return completed.stdout


def _checked(revision: str) -> str:
    if not revision or revision.startswith("-"):
        raise ValidationError(f"Invalid git revision '{revision}'.")
    return revision


def commit_state(revision: str, cwd: Path) -> dict[str, Any]:
    """Return the ``triage_change`` state for one commit.

    Raises:
        ValidationError: If git fails or *revision* is not a revision.
    """
    rev = _checked(revision)
    message = _git(["show", "-s", "--format=%B", rev, "--"], cwd)
    numstat = _git(["show", "--numstat", "--format=", rev, "--"], cwd)
    title, _, body = message.strip().partition("\n")
    files: list[str] = []
    additions = deletions = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        # Binary files report "-" for both counts.
        additions += int(added) if added.isdigit() else 0
        deletions += int(deleted) if deleted.isdigit() else 0
        files.append(path)
    return {
        "title": title.strip(),
        "description": body.strip()[:MAX_DESCRIPTION],
        "files": files[:MAX_FILES],
        "additions": additions,
        "deletions": deletions,
    }


def commits_in_range(revision_range: str, cwd: Path, limit: int) -> list[str]:
    """Return up to *limit* commit hashes in *revision_range*, oldest first.

    Merge commits are skipped: their changes are already in their parents.
    """
    out = _git(
        ["rev-list", "--no-merges", "--reverse", _checked(revision_range), "--"], cwd
    )
    return out.split()[-limit:] if limit else out.split()
