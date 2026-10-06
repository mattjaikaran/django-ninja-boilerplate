#!/usr/bin/env python
"""Check that docs/openapi/openapi.json is a complete type contract.

The frontend generates its Zod schemas and client from this file with
``@hey-api/openapi-ts``, so the Zod side has the same fields, required-ness,
nullability, and constraints as long as OpenAPI carries them. This gate checks
the OpenAPI side, without the frontend repo:

- PROPERTY_CASE: component property names are camelCase (CamelCaseSchema
  aliases reached the export).
- UNTYPED: every property and union member declares a type (``type``,
  ``$ref``, ``anyOf``, ``oneOf``, ``allOf``, ``enum``, or ``const``). An
  empty schema is ``Any`` and generates ``z.unknown()`` for the whole field.
- REQUIRED_DEFAULT: a required property has no default.
- NULL_DEFAULT: a property whose default is null is nullable.
- REQUIRED_UNKNOWN: every ``required`` name is a declared property.
- DANGLING_REF: every ``$ref`` resolves to a component.

Free-form container content (``list[Any]`` items, ``dict[str, Any]``
values) is allowed here: the source-level ``SCHEMA_ANY`` convention check
requires a ``# schema-ok:`` reason for it. Run ``just openapi-check`` first
so this file matches the code.

Usage:
    python scripts/check_schema_parity.py [path/to/openapi.json]

Exit codes: 0 pass, 1 violations, 2 missing or unreadable file.
"""

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC = PROJECT_ROOT / "docs" / "openapi" / "openapi.json"

CAMEL_CASE = re.compile(r"^[a-z][a-zA-Z0-9]*$")
TYPE_KEYS = {"type", "$ref", "anyOf", "oneOf", "allOf", "enum", "const"}
REF_PREFIX = "#/components/schemas/"

#: (component, property) pairs owned by third-party packages, with a reason.
ALLOWED_PROPERTY_NAMES = {
    ("DynamicInput", "page_size"): "ninja-extra pagination query input",
}


def _is_nullable(schema: dict[str, Any]) -> bool:
    if schema.get("nullable") is True or schema.get("type") == "null":
        return True
    members = schema.get("anyOf", []) + schema.get("oneOf", [])
    return any(m.get("type") == "null" for m in members)


def _untyped(schema: Any, where: str) -> Iterator[str]:
    """Yield locations of property or union-member schemas without a type."""
    if not isinstance(schema, dict) or not TYPE_KEYS & schema.keys():
        yield where
        return
    for key in ("anyOf", "oneOf", "allOf"):
        for i, member in enumerate(schema.get(key, [])):
            yield from _untyped(member, f"{where}.{key}[{i}]")


def _refs(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


def check(spec: dict[str, Any]) -> list[str]:
    """Return one ``[CHECK] location: message`` line per violation."""
    violations: list[str] = []
    components: dict[str, Any] = spec.get("components", {}).get("schemas", {})

    for name in sorted(components):
        component = components[name]
        properties: dict[str, Any] = component.get("properties", {})
        required = set(component.get("required", []))

        for missing in sorted(required - properties.keys()):
            violations.append(
                f"[REQUIRED_UNKNOWN] {name}: '{missing}' is not a property"
            )

        for prop, schema in properties.items():
            where = f"{name}.{prop}"
            if (
                not CAMEL_CASE.match(prop)
                and (name, prop) not in ALLOWED_PROPERTY_NAMES
            ):
                violations.append(f"[PROPERTY_CASE] {where}: not camelCase")
            violations.extend(
                f"[UNTYPED] {loc}: no type, generates z.unknown()"
                for loc in _untyped(schema, where)
            )
            if prop in required and "default" in schema:
                violations.append(
                    f"[REQUIRED_DEFAULT] {where}: required with a default"
                )
            if (
                "default" in schema
                and schema["default"] is None
                and not _is_nullable(schema)
            ):
                violations.append(f"[NULL_DEFAULT] {where}: default null, not nullable")

    for ref in sorted(set(_refs(spec))):
        if not ref.startswith(REF_PREFIX) or ref[len(REF_PREFIX) :] not in components:
            violations.append(f"[DANGLING_REF] {ref}: no such component")
    return violations


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_SPEC
    try:
        spec = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read {path}: {exc}. Run `just openapi`.")
        return 2

    violations = check(spec)
    for line in violations:
        print(line)
    count = len(spec.get("components", {}).get("schemas", {}))
    if violations:
        print(f"\n{len(violations)} schema parity violation(s) in {count} components.")
        return 1
    print(f"Schema parity OK: {count} components.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
