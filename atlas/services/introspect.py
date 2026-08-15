"""Introspection of the live API: OpenAPI operations, packets, edges, trace.

This module answers "what does the API expose and how do the pieces talk".
It extracts operations from the Ninja OpenAPI schema, maps them to app
labels, and builds the graph edges, clickable data packets, and the
canonical request-flow trace that the atlas renders.
"""

from __future__ import annotations

from typing import Any

from atlas.services.samples import mock_value, real_request_samples

MAX_EDGE_PACKETS = 4
MAX_CLIENT_PACKETS = 5


def _openapi_operations() -> list[dict[str, Any]]:
    """Extract operations from the live Ninja OpenAPI schema."""
    try:
        from api.urls import api  # lazy import avoids a module cycle

        schema = api.get_openapi_schema()
    except Exception:
        return []
    components = schema.get("components", {})
    operations = []
    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "tags": operation.get("tags", []),
                    "summary": operation.get("summary", "")
                    or operation.get("operationId", ""),
                    "request": _request_sample(operation, components),
                    "response": _response_sample(operation, components),
                    "status": _status_code(operation),
                }
            )
    return operations


def _request_sample(operation: dict[str, Any], components: dict[str, Any]) -> Any:
    schema = (
        operation.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    if not schema:
        return None
    return mock_value(schema, components, "payload")


def _response_sample(operation: dict[str, Any], components: dict[str, Any]) -> Any:
    responses = operation.get("responses", {})
    for code in (200, 201, 202, 204):
        response = responses.get(code) or responses.get(str(code)) or {}
        schema = response.get("content", {}).get("application/json", {}).get("schema")
        if schema:
            return mock_value(schema, components, "payload")
    return None


def _status_code(operation: dict[str, Any]) -> int:
    for code in (200, 201, 202, 204):
        if code in operation.get("responses", {}) or str(code) in operation.get(
            "responses", {}
        ):
            return code
    return 200


def _slug(operation: dict[str, Any]) -> str:
    path = (
        operation["path"].strip("/").replace("/", "-").replace("{", "").replace("}", "")
    )
    return f"{operation['method'].lower()}-{path or 'root'}"[:60]


def map_operations_to_apps(
    operations: list[dict[str, Any]],
    local_configs: list[Any],
    controller_names: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    """Map OpenAPI operations to app labels via tags and controller names."""
    app_labels = {config.label for config in local_configs}
    by_app: dict[str, list[dict[str, Any]]] = {}
    for op in operations:
        app_label = None
        for tag in op["tags"]:
            norm = tag.lower().replace("_", "").replace(" ", "")
            if norm in app_labels:
                app_label = norm
                break
            for ctrl_norm, label in controller_names.items():
                if norm == ctrl_norm or norm.startswith(ctrl_norm):
                    app_label = label
                    break
            if app_label:
                break
        by_app.setdefault(app_label or "api", []).append(op)
    return by_app


def build_packets(
    by_app: dict[str, list[dict[str, Any]]], include_real_samples: bool
) -> list[dict[str, Any]]:
    """Build data packets from schema shapes and (optionally) the audit log."""
    packets: list[dict[str, Any]] = []
    for app_label, ops in by_app.items():
        for op in ops:
            packets.append(
                {
                    "id": f"schema-{_slug(op)}",
                    "label": f"{op['method']} {op['path']}",
                    "method": op["method"],
                    "path": op["path"],
                    "app": app_label,
                    "source": "schema",
                    "payload": {
                        "request": op["request"],
                        "response": op["response"],
                        "status": op["status"],
                    },
                }
            )
    if include_real_samples:
        packets.extend(real_request_samples())
    return packets


def _edge_packets(ops: list[dict[str, Any]], packet_ids: set[str]) -> list[str]:
    """Pick schema packet ids for write operations on an app's endpoints."""
    ids = []
    for op in ops:
        if op["method"] not in ("POST", "PUT", "PATCH"):
            continue
        packet_id = f"schema-{_slug(op)}"
        if packet_id in packet_ids:
            ids.append(packet_id)
        if len(ids) >= MAX_EDGE_PACKETS:
            break
    return ids


def build_edges(
    by_app: dict[str, list[dict[str, Any]]],
    local_configs: list[Any],
    packets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build directed edges between structures and externals."""
    edges: list[dict[str, Any]] = []
    packet_ids = {packet["id"] for packet in packets}

    client_packets = [
        packet["id"]
        for packet in packets
        if packet["source"] == "schema" and packet["method"] in ("POST", "PUT", "PATCH")
    ][:MAX_CLIENT_PACKETS]
    edges.append(
        {
            "f": "client",
            "t": "api",
            "flow": 1,
            "pay": "REST / JSON (JWT)",
            "packets": client_packets,
        }
    )

    for config in local_configs:
        label = config.label
        ops = by_app.get(label, [])
        if not ops:
            continue
        edges.append(
            {
                "f": "api",
                "t": label,
                "flow": 1,
                "pay": "Controller routes",
                "packets": _edge_packets(ops, packet_ids),
            }
        )
        if config.get_models():
            edges.append(
                {
                    "f": label,
                    "t": "db",
                    "flow": 1,
                    "dashed": 1,
                    "pay": "ORM read/write",
                    "packets": [],
                }
            )
        if _has_tasks(config):
            edges.append(
                {
                    "f": label,
                    "t": "celery",
                    "flow": 1,
                    "dashed": 1,
                    "pay": "Background jobs",
                    "packets": [],
                }
            )

    edges.append(
        {
            "f": "api",
            "t": "valkey",
            "flow": 1,
            "dashed": 1,
            "pay": "Cache / throttle",
            "packets": [],
        }
    )
    edges.append(
        {
            "f": "api",
            "t": "centrifugo",
            "flow": 1,
            "dashed": 1,
            "pay": "Realtime publish",
            "packets": [],
        }
    )
    if "core" in by_app:
        edges.append(
            {
                "f": "core",
                "t": "email",
                "flow": 1,
                "dashed": 1,
                "pay": "Transactional email",
                "packets": [],
            }
        )
    if "billing" in by_app:
        edges.append(
            {
                "f": "billing",
                "t": "stripe",
                "flow": 1,
                "dashed": 1,
                "pay": "Checkout / subscriptions",
                "packets": [],
            }
        )
    if "files" in by_app:
        edges.append(
            {
                "f": "files",
                "t": "s3",
                "flow": 1,
                "dashed": 1,
                "pay": "Presigned uploads",
                "packets": [],
            }
        )
    return edges


def _has_tasks(config: Any) -> bool:
    """Return True when the app ships Celery tasks."""
    from pathlib import Path

    root = Path(config.path)
    return (root / "tasks.py").exists() or (root / "tasks").is_dir()


def build_trace(
    by_app: dict[str, list[dict[str, Any]]], local_configs: list[Any]
) -> list[list[str]]:
    """Build a canonical request-flow trace for the primary app."""
    primary = next(
        (
            config
            for config in local_configs
            if config.label == "todos" and config.label in by_app
        ),
        next(
            (config for config in local_configs if config.label in by_app),
            None,
        ),
    )
    if primary is None:
        return []
    ops = by_app.get(primary.label, [])
    post = next(
        (op for op in ops if op["method"] in ("POST", "PUT")),
        ops[0] if ops else None,
    )
    if post is None:
        return []
    models = list(primary.get_models())
    model_name = models[0].__name__ if models else "record"
    return [
        ["client", f"Client sends {post['method']} {post['path']} with a JSON payload"],
        ["api", "Route matches; JWT auth verifies the caller"],
        [
            primary.label,
            f"{primary.label} controller validates and delegates to its service",
        ],
        [primary.label, "Service applies business rules and scopes data to the user"],
        [primary.label, f"ORM writes a {model_name} row"],
        ["db", "PostgreSQL persists the transaction"],
        ["core", "AuditLog records the API_REQUEST entry"],
        ["client", f"Response {post['status']} returns the serialized payload"],
    ]
