"""Locate the django-ninja-boilerplate project that holds manage.py."""

from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path) -> Path | None:
    """Return the nearest directory at or above ``start`` that holds manage.py."""
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "manage.py").is_file():
            return candidate
    return None
