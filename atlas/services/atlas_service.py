"""Generate atlas data by introspecting the running Django project.

The generator scans the installed local apps, counts lines of code, reads
models and API routes, and emits the JSON contract the admin renderer
consumes. Run ``python manage.py atlas`` to write the data file, or let
the admin page generate it lazily.

Every number in the rendered map comes from this scan. Nothing is invented:
sizes come from real line counts, endpoints from the OpenAPI schema, and
data packets from schema shapes plus masked audit-log samples.
"""

from __future__ import annotations

import importlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Any

from django import get_version
from django.apps import apps as django_apps
from django.conf import settings

from atlas.services.introspect import (
    _openapi_operations,
    build_edges,
    build_packets,
    build_trace,
    map_operations_to_apps,
)
from atlas.services.layout import assign_layout, height_for_child

GROUPS = [
    {"id": "interface", "name": "Interface", "color": "#38bdf8"},
    {"id": "api", "name": "API Layer", "color": "#a78bfa"},
    {"id": "app", "name": "Applications", "color": "#34d399"},
    {"id": "infra", "name": "Infrastructure", "color": "#fbbf24"},
]

EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    ".pytest_cache",
    "node_modules",
    "env",
    ".venv",
    "htmlcov",
    "dist",
    "build",
    ".context",
}

COMPONENT_DIRS = ("controllers", "services", "models", "schemas", "admin")
MAX_MODEL_NAMES = 14


def _base_dir() -> Path:
    return Path(settings.BASE_DIR)


def count_loc(root: Path) -> int:
    """Count lines in Python files under ``root``."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            try:
                with (Path(dirpath) / filename).open(
                    encoding="utf-8", errors="ignore"
                ) as handle:
                    total += sum(1 for _ in handle)
            except OSError:
                continue
    return total


def _file_loc(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def _count_test_files() -> int:
    """Count test modules under the project root."""
    total = 0
    for _dirpath, dirnames, filenames in os.walk(_base_dir()):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for filename in filenames:
            if filename.endswith(".py") and (
                filename.startswith("test_") or filename.endswith("_test.py")
            ):
                total += 1
    return total


def _local_app_configs() -> list[Any]:
    """Return AppConfigs for apps that live inside the project directory."""
    base = _base_dir().resolve()
    configs = []
    for config in django_apps.get_app_configs():
        try:
            path = Path(config.path).resolve()
        except (AttributeError, OSError):
            continue
        if "site-packages" in path.parts or ".venv" in path.parts:
            continue
        if path.is_relative_to(base):
            configs.append(config)
    return configs


def metadata_for(label: str) -> dict[str, Any]:
    """Read prose metadata from ``settings.ATLAS_METADATA`` or ``<app>.atlas``.

    The generator cannot guess what an app does. Adopters fill in a small
    ``atlas.py`` module per app (see ``todos/atlas.py``) or set
    ``ATLAS_METADATA`` in settings; the generator falls back to the app
    label when neither exists.
    """
    configured = getattr(settings, "ATLAS_METADATA", None)
    if isinstance(configured, dict) and label in configured:
        return configured[label] or {}
    try:
        module = importlib.import_module(f"{label}.atlas")
    except (ImportError, ModuleNotFoundError):
        return {}
    return getattr(module, "ATLAS", {}) or {}


def _controller_names(local_configs: list[Any]) -> dict[str, str]:
    """Map normalized controller class names to app labels."""
    controller_names: dict[str, str] = {}
    for config in local_configs:
        try:
            module = importlib.import_module(f"{config.label}.controllers")
        except (ImportError, ModuleNotFoundError):
            continue
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and name.endswith("Controller"):
                norm = name.removesuffix("Controller").lower().replace("_", "")
                controller_names.setdefault(norm, config.label)
    return controller_names


def _build_api_structure(
    operations: list[dict[str, Any]], by_app: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Build the API layer structure from the project package."""
    api_root = Path(settings.BASE_DIR) / "api"
    children = [
        {
            "code": "UR",
            "name": "URLs",
            "h": height_for_child(_file_loc(api_root / "urls.py")),
            "what": "NinjaExtraAPI instance + controller registration",
            "loc": _file_loc(api_root / "urls.py"),
        },
        {
            "code": "MW",
            "name": "Middleware",
            "h": height_for_child(_file_loc(api_root / "middleware.py")),
            "what": "Observability, audit, security headers, throttling",
            "loc": _file_loc(api_root / "middleware.py"),
        },
        {
            "code": "DC",
            "name": "Decorators",
            "h": height_for_child(_file_loc(api_root / "decorators.py")),
            "what": "handle_exceptions, log_api_call, validate_request",
            "loc": _file_loc(api_root / "decorators.py"),
        },
        {
            "code": "ST",
            "name": "Settings",
            "h": height_for_child(count_loc(api_root / "settings")),
            "what": "Split settings: common, dev, prod, test, unfold",
            "loc": count_loc(api_root / "settings"),
        },
    ]
    return {
        "id": "api",
        "code": "API",
        "name": "API Layer",
        "group": "api",
        "loc": count_loc(api_root),
        "what": "Django Ninja API — routing, auth, middleware, decorators",
        "how": "The NinjaExtraAPI instance in api/urls.py registers every "
        "controller. Middleware adds observability, audit logging, security "
        "headers, and throttling.",
        "stats": {"models": 0, "model_names": [], "endpoints": len(operations)},
        "talks": sorted(by_app),
        "children": children,
        "w": 2,
        "d": 1,
    }


def _build_structure(
    config: Any, by_app: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Build a structure node for one installed local app."""
    label = config.label
    meta = metadata_for(label)
    models = list(config.get_models())
    app_ops = by_app.get(label, [])
    verbose_name = str(getattr(config, "verbose_name", None) or "")
    fallback_name = label.replace("_", " ").title()
    name = meta.get("name") or (verbose_name or fallback_name)
    return {
        "id": label,
        "code": meta.get("code", label[:2].upper()),
        "name": name,
        "group": meta.get("group", "app"),
        "loc": count_loc(Path(config.path)),
        "what": meta.get("what", f"{label} application"),
        "how": meta.get("how", ""),
        "stats": {
            "models": len(models),
            "model_names": [model.__name__ for model in models][:MAX_MODEL_NAMES],
            "endpoints": len(app_ops),
        },
        "talks": meta.get("talks", []),
        "children": _children_for(config, meta),
        "w": meta.get("w", 1),
        "d": meta.get("d", 1),
    }


def _children_for(config: Any, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Build inside-view blocks for an app's layered components."""
    root = Path(config.path)
    components = []
    for name in COMPONENT_DIRS:
        path = root / name
        if not path.exists():
            continue
        comp_loc = count_loc(path)
        comp_meta = meta.get("children", {}).get(name, {})
        components.append(
            {
                "code": comp_meta.get("code", name[:2].upper()),
                "name": comp_meta.get("name", name.title()),
                "h": height_for_child(comp_loc),
                "what": comp_meta.get(
                    "what", f"{name} layer — {comp_loc} lines of code"
                ),
                "loc": comp_loc,
            }
        )
    tasks_path = root / "tasks.py"
    tasks_dir = root / "tasks"
    if tasks_path.exists() or tasks_dir.is_dir():
        task_loc = _file_loc(tasks_path) + (
            count_loc(tasks_dir) if tasks_dir.is_dir() else 0
        )
        components.append(
            {
                "code": "TK",
                "name": "Tasks",
                "h": height_for_child(task_loc),
                "what": f"Celery background tasks — {task_loc} lines",
                "loc": task_loc,
            }
        )
    return components


def _build_externals(
    by_app: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Build external nodes: clients on top, infrastructure at the bottom."""
    externals = [
        {
            "id": "client",
            "name": "Web / Mobile Clients",
            "group": "interface",
            "zone": "client",
            "dashed": 1,
            "what": "Browsers, mobile apps, and third-party callers",
            "how": "Authenticates with JWT bearer tokens and calls REST endpoints.",
        },
        {
            "id": "db",
            "name": "PostgreSQL",
            "group": "infra",
            "zone": "infra",
            "dashed": 1,
            "w": 2,
            "what": "Primary database",
            "how": "All model rows persist here; UUIDv7 primary keys.",
        },
        {
            "id": "valkey",
            "name": "Valkey",
            "group": "infra",
            "zone": "infra",
            "dashed": 1,
            "w": 2,
            "what": "Cache + broker",
            "how": "Sessions, throttling counters, and the Celery broker.",
        },
        {
            "id": "celery",
            "name": "Celery Workers",
            "group": "infra",
            "zone": "infra",
            "dashed": 1,
            "w": 2,
            "what": "Background task workers",
            "how": "Emails, digests, webhook delivery, scheduled jobs.",
        },
        {
            "id": "centrifugo",
            "name": "Centrifugo",
            "group": "infra",
            "zone": "infra",
            "dashed": 1,
            "w": 2,
            "what": "Realtime server",
            "how": "WebSocket channels, presence, and history with JWT auth.",
        },
        {
            "id": "email",
            "name": "Email (Resend)",
            "group": "infra",
            "zone": "infra",
            "dashed": 1,
            "w": 2,
            "what": "Transactional email",
            "how": "Template-based email service with multiple backends.",
        },
    ]
    if "billing" in by_app:
        externals.append(
            {
                "id": "stripe",
                "name": "Stripe",
                "group": "infra",
                "zone": "infra",
                "dashed": 1,
                "w": 2,
                "what": "Payments",
                "how": "Checkout sessions, subscriptions, webhooks.",
            }
        )
    if "files" in by_app:
        externals.append(
            {
                "id": "s3",
                "name": "Object Storage (S3)",
                "group": "infra",
                "zone": "infra",
                "dashed": 1,
                "w": 2,
                "what": "File storage",
                "how": "Presigned uploads and public media.",
            }
        )
    return externals


def _build_meta(
    structures: list[dict[str, Any]], operations: list[dict[str, Any]]
) -> dict[str, Any]:
    total_loc = sum(structure["loc"] for structure in structures)
    model_count = sum(structure["stats"]["models"] for structure in structures)
    return {
        "project": _base_dir().name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_loc": total_loc,
        "app_count": len(structures),
        "endpoint_count": len(operations),
        "model_count": model_count,
        "test_files": _count_test_files(),
        "django": get_version(),
        "python": platform.python_version(),
    }


def generate_atlas(*, include_real_samples: bool | None = None) -> dict[str, Any]:
    """Generate the full atlas data structure for the running project."""
    if include_real_samples is None:
        include_real_samples = getattr(settings, "ATLAS_REAL_SAMPLES", True)

    local_configs = _local_app_configs()
    operations = _openapi_operations()
    controller_names = _controller_names(local_configs)
    by_app = map_operations_to_apps(operations, local_configs, controller_names)

    structures = [_build_api_structure(operations, by_app)]
    for config in local_configs:
        if config.label == "atlas":
            continue  # the tool does not map itself
        structures.append(_build_structure(config, by_app))

    externals = _build_externals(by_app)
    packets = build_packets(by_app, include_real_samples)
    edges = build_edges(by_app, local_configs, packets)
    trace = build_trace(by_app, local_configs)

    assign_layout(structures, externals)
    meta = _build_meta(structures, operations)

    return {
        "meta": meta,
        "groups": GROUPS,
        "structures": structures,
        "externals": externals,
        "edges": edges,
        "packets": packets,
        "trace": trace,
    }


def load_or_generate(*, force: bool = False) -> dict[str, Any]:
    """Load the data file when fresh, otherwise regenerate and cache it."""
    default_path = Path(settings.BASE_DIR) / "atlas-data.json"
    path = Path(getattr(settings, "ATLAS_DATA_PATH", default_path))
    ttl = getattr(settings, "ATLAS_CACHE_TTL", 3600)

    if not force and path.exists():
        try:
            age = time.time() - path.stat().st_mtime
            if age < ttl:
                with path.open(encoding="utf-8") as handle:
                    return json.load(handle)
        except (OSError, json.JSONDecodeError):
            pass

    data = generate_atlas()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    except OSError:
        pass
    return data
