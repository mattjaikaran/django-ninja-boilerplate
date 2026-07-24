#!/usr/bin/env python3
"""Pre-commit hook to enforce maximum file length.

Configuration via pyproject.toml:

    [tool.file-length]
    max-lines = 400
    exclude = [
        "*/migrations/*",
        "*/management/commands/generators/*",
    ]
    # Per-pattern overrides (glob -> max lines)
    [tool.file-length.per-file-max]
    "scripts/*" = 800
    "cli/*" = 800

Per-file overrides via comments (in first 5 lines):
    # file-length-ignore          — skip this file entirely
    # file-length-max: 600        — override max for this file
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
import tomllib
from pathlib import Path


def load_config() -> dict:
    """Load [tool.file-length] from pyproject.toml."""
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        return {}

    with open(pyproject, "rb") as f:
        data = tomllib.load(f)

    return data.get("tool", {}).get("file-length", {})


def parse_file_directives(filepath: Path) -> dict:
    """Parse file-length directives from the first 5 lines."""
    directives: dict = {}
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= 5:
                    break
                stripped = line.strip()
                if "file-length-ignore" in stripped:
                    directives["ignore"] = True
                if "file-length-max:" in stripped:
                    try:
                        val = stripped.split("file-length-max:")[1].strip()
                        directives["max"] = int(val)
                    except (ValueError, IndexError):
                        pass
    except OSError:
        pass
    return directives


def count_lines(filepath: Path) -> int:
    """Count lines in a file."""
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def normalize_path(filepath: str) -> str:
    """Strip leading ./ from paths for consistent matching."""
    while filepath.startswith("./"):
        filepath = filepath[2:]
    return filepath


def match_pattern(filepath: str, pattern: str) -> bool:
    """Match filepath against a pattern, supporting recursive directory globs.

    Patterns like "scripts/*" match both direct children (scripts/foo.py)
    and nested paths (scripts/openapi/foo.py). Exact file paths match exactly.
    """
    if fnmatch.fnmatch(filepath, pattern):
        return True
    if "*" in pattern:
        prefix = pattern.split("*", maxsplit=1)[0].rstrip("/")
        if prefix and filepath.startswith(prefix + "/"):
            return True
    return False


def matches_any(filepath: str, patterns: list[str]) -> bool:
    """Check if filepath matches any glob pattern."""
    return any(match_pattern(filepath, pat) for pat in patterns)


def get_per_file_max(filepath: str, per_file_max: dict[str, int]) -> int | None:
    """Get per-file max from config patterns. Most specific match wins."""
    best_match: tuple[int, int | None] = (0, None)
    for pattern, max_lines in per_file_max.items():
        if match_pattern(filepath, pattern):
            specificity = len(pattern)
            if specificity > best_match[0]:
                best_match = (specificity, max_lines)
    return best_match[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check file length")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Maximum lines per file (default: 400, or from pyproject.toml)",
    )
    args = parser.parse_args()

    config = load_config()
    default_max = args.max_lines or config.get("max-lines", 400)
    exclude_patterns = config.get("exclude", [])
    per_file_max = config.get("per-file-max", {})

    failures = []

    for filepath_str in args.files:
        filepath_str = normalize_path(filepath_str)
        filepath = Path(filepath_str)

        if not filepath.exists() or not filepath.is_file():
            continue

        # Check global excludes
        if matches_any(filepath_str, exclude_patterns):
            continue

        # Check per-file directives
        directives = parse_file_directives(filepath)
        if directives.get("ignore"):
            continue

        # Determine max: directive > per-file config > default
        if "max" in directives:
            max_lines = directives["max"]
        else:
            per_file = get_per_file_max(filepath_str, per_file_max)
            max_lines = per_file if per_file is not None else default_max

        line_count = count_lines(filepath)

        if line_count > max_lines:
            failures.append((filepath_str, line_count, max_lines))

    if failures:
        print("File length check failed:")
        for filepath_str, count, max_lines in failures:
            print(f"  {filepath_str}: {count} lines (max {max_lines})")
        print()
        print("To fix, either:")
        print("  1. Refactor the file to reduce its length")
        print("  2. Add '# file-length-ignore' in the first 5 lines to skip")
        print("  3. Add '# file-length-max: N' in the first 5 lines to override")
        print("  4. Add an exclude pattern in [tool.file-length] in pyproject.toml")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
