"""Deterministic sample payloads and real audit-log data packets.

The atlas shows clickable data packets: snippets of real data transfer
between structures. Two sources feed the packets:

1. OpenAPI schema: request and response shapes generated from the live
   Pydantic schemas, filled with deterministic sample values.
2. Audit log: the most recent real request bodies recorded by the
   ``AuditLoggingMiddleware``. The middleware masks sensitive fields, and
   the atlas only shows request side payloads.

No packet ever carries a live secret: audit bodies are masked before they
reach the database, and schema samples are generated locally.
"""

from __future__ import annotations

import json
from typing import Any

_NAME_EXAMPLES = {
    "email": "user@example.com",
    "password": "[REDACTED]",
    "token": "[REDACTED]",
    "secret": "[REDACTED]",
    "api_key": "[REDACTED]",
    "apikey": "[REDACTED]",
    "authorization": "[REDACTED]",
    "phone": "+1-555-0100",
    "url": "https://example.com/resource",
    "avatar": "https://example.com/avatar.png",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "name": "Sample record",
    "title": "Sample title",
    "description": "Sample description",
    "status": "active",
    "role": "member",
}

MAX_SAMPLE_DEPTH = 5
MAX_PROPERTIES = 8


def resolve_ref(
    schema: dict[str, Any],
    components: dict[str, Any],
    seen: set[str] | None = None,
) -> dict[str, Any]:
    """Follow ``$ref`` chains inside an OpenAPI schema node."""
    ref = schema.get("$ref")
    if not ref:
        return schema
    seen = seen or set()
    if ref in seen:
        return {"type": "string", "description": "circular reference"}
    name = ref.rsplit("/", 1)[-1]
    target = components.get("schemas", {}).get(name, {})
    return resolve_ref(target, components, seen | {ref})


def mock_value(
    schema: dict[str, Any],
    components: dict[str, Any],
    field_name: str = "",
    depth: int = 0,
) -> Any:
    """Build a deterministic sample value from an OpenAPI JSON schema."""
    schema = resolve_ref(schema, components)
    if depth > MAX_SAMPLE_DEPTH:
        return "..."
    if "anyOf" in schema:
        for candidate in schema["anyOf"]:
            if candidate.get("type") != "null":
                return mock_value(candidate, components, field_name, depth)
    if "oneOf" in schema:
        return mock_value(schema["oneOf"][0], components, field_name, depth)
    if "allOf" in schema:
        merged: dict[str, Any] = {}
        for part in schema["allOf"]:
            merged.update(resolve_ref(part, components).get("properties", {}))
        if merged:
            return _mock_object(merged, components, depth)
    if schema.get("type") == "object" or "properties" in schema:
        return _mock_object(schema.get("properties", {}), components, depth)
    if schema.get("type") == "array":
        items = schema.get("items")
        return [mock_value(items, components, field_name, depth + 1)] if items else []
    if schema.get("type") == "integer":
        return 1
    if schema.get("type") == "number":
        return 1.5
    if schema.get("type") == "boolean":
        return True
    if schema.get("type") == "null":
        return None
    return _mock_string(schema, field_name)


def _mock_object(
    properties: dict[str, Any],
    components: dict[str, Any],
    depth: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value_schema in list(properties.items())[:MAX_PROPERTIES]:
        result[key] = mock_value(value_schema, components, key, depth + 1)
    return result


def _mock_string(schema: dict[str, Any], field_name: str) -> str:
    if schema.get("enum"):
        return schema["enum"][0]
    fmt = schema.get("format", "")
    if fmt == "uuid":
        return "3f2a1b4c-9d8e-4f7a-b6c5-1d2e3f4a5b6c"
    if fmt == "date-time":
        return "2026-08-14T12:00:00Z"
    if fmt == "date":
        return "2026-08-14"
    if fmt == "email":
        return "user@example.com"
    if fmt == "uri":
        return "https://example.com/resource"
    key = field_name.lower()
    for name, example in _NAME_EXAMPLES.items():
        if name in key:
            return example
    return field_name or "sample"


def real_request_samples(*, limit: int = 60) -> list[dict[str, Any]]:
    """Pull the most recent masked request bodies from the audit log.

    Returns one sample per request path, newest first, capped at 12.
    Empty when the audit app is unavailable or no bodies were captured.
    """
    try:
        from core.audit.models import AuditLog
    except ImportError:
        return []
    try:
        rows = list(
            AuditLog.objects.filter(
                action="API_REQUEST", extra_data__has_key="request_body"
            ).order_by("-timestamp")[:limit]
        )
    except Exception:
        # The atlas is a code scanner; a down database must not break it.
        return []
    seen_paths: set[str] = set()
    samples: list[dict[str, Any]] = []
    for row in rows:
        path = row.request_path or ""
        if path in seen_paths:
            continue
        seen_paths.add(path)
        body = row.extra_data.get("request_body", "")
        if not body:
            continue
        try:
            payload: Any = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            payload = {"raw_body": body[:500]}
        samples.append(
            {
                "id": f"real-{row.id.hex[:8]}",
                "label": f"Real request — {row.request_method} {path}",
                "method": row.request_method,
                "path": path,
                "source": "audit",
                "payload": payload,
                "at": row.timestamp.isoformat() if row.timestamp else "",
            }
        )
        if len(samples) >= 12:
            break
    return samples
