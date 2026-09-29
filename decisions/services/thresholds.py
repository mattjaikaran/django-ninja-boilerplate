"""Server-side per-question escalation thresholds.

``DECISION_THRESHOLDS_FILE`` names a JSON file keyed by provider, then by
question key::

    {"laya": {"team": 0.35, "urgent": 0.8}, "clm": {"team": 0.9}}

``recommend_thresholds --write`` fills it from eval output. Thresholds are
per provider because each provider's confidence has its own scale. A question
missing from the file uses ``DECISION_ESCALATION_THRESHOLD``.

Only operators can set these values. The API and MCP request schemas forbid
extra fields, so no client can send a threshold.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

#: Cache of parsed files, keyed by path and modification time.
_CACHE: dict[tuple[str, int], dict[str, dict[str, float]]] = {}


def _validated(raw: object, path: Path) -> dict[str, dict[str, float]]:
    if not isinstance(raw, dict):
        raise ImproperlyConfigured(f"{path} must hold an object keyed by provider.")
    table: dict[str, dict[str, float]] = {}
    for provider, questions in raw.items():
        if not isinstance(questions, dict):
            raise ImproperlyConfigured(
                f"{path}: '{provider}' must map question keys to thresholds."
            )
        section: dict[str, float] = {}
        table[str(provider)] = section
        for key, value in questions.items():
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ImproperlyConfigured(
                    f"{path}: threshold {provider}.{key} must be a number."
                )
            if not 0.0 <= value <= 1.0:
                raise ImproperlyConfigured(
                    f"{path}: threshold {provider}.{key}={value} is outside 0 to 1."
                )
            section[str(key)] = float(value)
    return table


def read_thresholds_file(path: Path) -> dict[str, dict[str, float]]:
    """Parse and validate a thresholds file.

    Raises:
        ImproperlyConfigured: If the file is missing, is not JSON, or holds a
            value that is not a number from 0 to 1.
    """
    try:
        stamp = path.stat().st_mtime_ns
    except OSError as exc:
        raise ImproperlyConfigured(
            f"DECISION_THRESHOLDS_FILE points to {path}, which cannot be read: {exc}"
        ) from exc
    cached = _CACHE.get((str(path), stamp))
    if cached is not None:
        return cached
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ImproperlyConfigured(f"{path} is not valid JSON: {exc}") from exc
    table = _validated(raw, path)
    _CACHE[(str(path), stamp)] = table
    return table


def question_thresholds(provider: str) -> dict[str, float]:
    """Return the configured per-question thresholds for *provider*.

    Returns an empty mapping when ``DECISION_THRESHOLDS_FILE`` is empty.
    """
    configured = getattr(settings, "DECISION_THRESHOLDS_FILE", "")
    if not configured:
        return {}
    return read_thresholds_file(Path(configured)).get(provider, {})


def write_provider_thresholds(
    path: Path, provider: str, thresholds: dict[str, float]
) -> dict[str, dict[str, float]]:
    """Replace *provider*'s section in *path*, keeping other providers.

    Returns:
        The full table that was written.
    """
    table = read_thresholds_file(path) if path.exists() else {}
    table = {**table, provider: dict(sorted(thresholds.items()))}
    _validated(table, path)
    path.write_text(json.dumps(dict(sorted(table.items())), indent=2) + "\n")
    return table
