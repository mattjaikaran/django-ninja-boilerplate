#!/usr/bin/env python3
"""Audit gate: run pip-audit on every locked package and fail on any advisory.

The audit reads ``uv.lock`` (all extras, hashed) instead of the local virtual
environment, so the result does not depend on which extras you installed.

Known advisories that have no fix yet go in ``pip-audit-allowlist.toml``. Each
entry needs an ``id``, a ``reason`` and an ``expires`` date. An expired entry
fails the gate, so every exception gets reviewed again.

Usage:
    uv run --extra dev python scripts/audit_dependencies.py

Exit: 0 = no unlisted advisory, 1 = advisory found or allow-list invalid/expired
"""

from __future__ import annotations

import datetime
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = PROJECT_ROOT / "pip-audit-allowlist.toml"


def allowed_ids(today: datetime.date) -> tuple[list[str], list[str]]:
    """Return (advisory IDs to ignore, allow-list errors)."""
    if not ALLOWLIST.is_file():
        return [], []
    entries = tomllib.loads(ALLOWLIST.read_text(encoding="utf-8")).get("ignore", [])
    ids: list[str] = []
    errors: list[str] = []
    for entry in entries:
        advisory = entry.get("id", "<missing id>")
        expires = entry.get("expires")
        if not entry.get("reason"):
            errors.append(f"{advisory}: add a reason")
        if not isinstance(expires, datetime.date):
            errors.append(f"{advisory}: add expires = YYYY-MM-DD")
        elif expires < today:
            errors.append(f"{advisory}: allow-list entry expired on {expires}")
        else:
            ids.append(advisory)
    return ids, errors


def main() -> int:
    ids, errors = allowed_ids(datetime.datetime.now(datetime.UTC).date())
    if errors:
        for error in errors:
            print(f"  FAIL {ALLOWLIST.name}: {error}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        requirements = Path(tmp) / "requirements.txt"
        subprocess.run(
            [
                "uv",
                "export",
                "--frozen",
                "--all-extras",
                "--no-emit-project",
                "--quiet",
                "--output-file",
                str(requirements),
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )
        command = [
            sys.executable,
            "-m",
            "pip_audit",
            "--requirement",
            str(requirements),
            "--disable-pip",
            "--progress-spinner",
            "off",
        ]
        for advisory in ids:
            command += ["--ignore-vuln", advisory]
        if ids:
            print(f"  Ignoring allow-listed advisories: {', '.join(ids)}")
        # Argument list, no shell; IDs come from the committed allow-list.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        return subprocess.run(command, cwd=PROJECT_ROOT, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
