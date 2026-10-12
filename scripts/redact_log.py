#!/usr/bin/env python3
"""Redact secrets from a log before it leaves the machine (for example, a PR body).

A worker model pastes failure logs into draft PRs. Pytest and gauntlet output
can echo settings, connection strings or tokens. This filter replaces:

- the value of every secret-looking key in `.env` and `.env.development`
  (names containing SECRET, PASSWORD, TOKEN, KEY, DSN, URL or AUTH),
- bearer tokens, URLs with credentials, and common token formats.

Usage:
    tail -n 50 ~/.cache/worker-once/verify.log | uv run python scripts/redact_log.py > ~/.cache/worker-once/T-NNN-failure.md

Exit: 0 always; the redacted text goes to stdout.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILES = (".env", ".env.development")
SECRET_NAME = re.compile(r"SECRET|PASSWORD|TOKEN|KEY|DSN|URL|AUTH", re.IGNORECASE)
# Short values (ports, "true") would redact unrelated text.
MIN_VALUE_LENGTH = 6
PATTERNS = (
    (re.compile(r"(?i)(bearer\s+)[\w.~+/=-]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(authorization:\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(\w+://)[^\s/:@]+:[^\s/@]+@"), r"\1[REDACTED]@"),
    (re.compile(r"\b(ghp|gho|ghs|ghu)_\w{20,}"), "[REDACTED:github]"),
    (re.compile(r"\bgithub_pat_\w{20,}"), "[REDACTED:github]"),
    (re.compile(r"\b(sk|rk|pk)_(live|test)_\w{10,}"), "[REDACTED:stripe]"),
    (re.compile(r"\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}"), "[REDACTED:jwt]"),
)


def secret_values(root: Path) -> dict[str, str]:
    """Return {value: key} for secret-looking keys in the env files."""
    values: dict[str, str] = {}
    for name in ENV_FILES:
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            key, sep, raw = line.partition("=")
            key = key.strip().removeprefix("export ").strip()
            if not sep or key.startswith("#") or not SECRET_NAME.search(key):
                continue
            value = raw.strip().strip("'\"")
            if len(value) >= MIN_VALUE_LENGTH:
                values[value] = key
    return values


def redact(text: str, values: dict[str, str]) -> str:
    """Apply the patterns, then replace known values (longest first).

    Patterns run first: a short value such as `postgres` would otherwise
    break the URL-with-credentials pattern before it can match.
    """
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, f"[REDACTED:{values[value]}]")
    return text


def main() -> int:
    sys.stdout.write(redact(sys.stdin.read(), secret_values(PROJECT_ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
