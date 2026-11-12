#!/usr/bin/env python3
"""Architecture enforcement for the Django Ninja Boilerplate.

Validates layered architecture constraints:
  Controllers → Services → Repositories → Models (no reverse deps)

Also detects cross-app controller coupling, enforces module boundaries, and
checks the optional engine layer (engines/<engine>/<module>/).

Works in both standalone boilerplate and mattstack-scaffolded projects
(where the boilerplate lives under backend/).

Usage:
    python scripts/check_architecture.py [files...]
    python scripts/check_architecture.py --all
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Layer definitions ────────────────────────────────────────────────────────
LAYERS: dict[str, int] = {
    "controllers": 4,
    "services": 3,
    "repositories": 2,
    "schemas": 2,
    "tasks": 2,
    "dtos": 1,
    "models": 1,
    "migrations": 0,
}

# Apps in the project (auto-detected, with these as seed list)
KNOWN_APPS = {
    "core",
    "todos",
    "billing",
    "files",
    "webhooks",
    "organizations",
    "notifications",
}

ALLOWED_CROSS_IMPORTS = {
    "api.permissions",
    "api.schemas",
    "api.throttling",
    "api.decorators",
    "api.tasks",
}

FORBIDDEN_LAYER_DEPS = [
    ("models", "controllers"),
    ("models", "services"),
    ("models", "schemas"),
    ("controllers", "repositories"),
    ("services", "controllers"),
    ("repositories", "controllers"),
    ("repositories", "services"),
    ("repositories", "schemas"),
    ("migrations", "controllers"),
    ("migrations", "services"),
    ("migrations", "schemas"),
    ("dtos", "models"),
    ("dtos", "repositories"),
    ("dtos", "services"),
    ("dtos", "schemas"),
    ("dtos", "controllers"),
]

# Optional engine layer: engines/<engine>/<module>/ is a Django app, and
# engines/<engine>/services/ holds the engine-level orchestration.
ENGINES_DIR = "engines"

# The composition root wires engine controllers into the API. Only files
# under this top-level package may import another module's controllers.
COMPOSITION_ROOT = "api"

SKIP_DIRS = {
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    "cli",
}


@dataclass
class Violation:
    filepath: str
    line: int
    rule: str
    message: str


def _detect_apps(root: Path) -> set[str]:
    """Auto-detect Django apps by looking for apps.py or models/ directories."""
    apps = set(KNOWN_APPS)
    for candidate in root.iterdir():
        if not candidate.is_dir() or candidate.name.startswith("."):
            continue
        if candidate.name in SKIP_DIRS:
            continue
        if (candidate / "apps.py").exists() or (candidate / "models").is_dir():
            apps.add(candidate.name)
    return apps


def _dotted_parts(path: str) -> tuple[str, ...]:
    """Return a file path as parts, without the backend/ prefix or .py suffix."""
    return Path(path.removeprefix("backend/")).with_suffix("").parts


def _engine_position(
    parts: tuple[str, ...] | list[str],
) -> tuple[str | None, str | None, str | None]:
    """Return (engine, module, next part) for an engines path or import.

    A module is the segment after the engine, unless that segment is a layer
    name: then the code is engine-level. Returns (None, None, None) outside
    the engines directory.
    """
    if len(parts) < 2 or parts[0] != ENGINES_DIR:
        return None, None, None
    engine = parts[1]
    if len(parts) < 3:
        return engine, None, None
    if parts[2] in LAYERS:
        return engine, None, parts[2]
    return engine, parts[2], parts[3] if len(parts) > 3 else None


def _resolve_from(file_parts: tuple[str, ...], node: ast.ImportFrom) -> str:
    """Return the absolute dotted name of a ``from`` import."""
    if node.level == 0:
        return node.module or ""
    package = file_parts[:-1]
    parts = list(package[: max(len(package) - (node.level - 1), 0)])
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts)


def _import_targets(
    node: ast.Import | ast.ImportFrom, file_parts: tuple[str, ...]
) -> list[str]:
    """Return the absolute dotted names an import statement reaches.

    For ``from pkg import name`` where ``pkg`` is a package root, each name is
    a candidate submodule, so ``from engines.e.m import services`` is checked
    as ``engines.e.m.services``.
    """
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    base = _resolve_from(file_parts, node)
    if not base:
        return []
    engine, _, head = _engine_position(base.split("."))
    if engine is None or head is not None:
        return [base]
    return [f"{base}.{alias.name}" for alias in node.names if alias.name != "*"] or [
        base
    ]


@dataclass
class ArchChecker:
    violations: list[Violation] = field(default_factory=list)
    files_checked: int = 0
    apps: set[str] = field(default_factory=set)

    def check_file(self, filepath: Path) -> None:
        """Check a single Python file for architecture violations."""
        relative = str(filepath)

        # Skip test files — tests can import freely
        parts = filepath.parts
        if any(p in ("tests", "test") for p in parts) or filepath.name.startswith(
            "test_"
        ):
            return
        # Skip conftest, migrations init, __init__ re-exports
        if filepath.name == "conftest.py":
            return

        self.files_checked += 1

        try:
            source = filepath.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(filepath))
        except (SyntaxError, UnicodeDecodeError):
            return

        from_layer = self._identify_layer(relative)
        file_parts = _dotted_parts(relative)
        self._check_engine_layout(relative, filepath, file_parts)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_import(relative, node.lineno, from_layer, alias.name)
                self._check_module_boundary(
                    relative, node.lineno, file_parts, _import_targets(node, file_parts)
                )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._check_import(relative, node.lineno, from_layer, node.module)
                self._check_module_boundary(
                    relative, node.lineno, file_parts, _import_targets(node, file_parts)
                )

    def _identify_layer(self, filepath: str) -> str | None:
        """Identify which architectural layer a file belongs to."""
        # Strip backend/ prefix for mattstack projects
        normalized = filepath.removeprefix("backend/")
        for part in Path(normalized).parts:
            if part in LAYERS:
                return part
        return None

    def _identify_app(self, filepath: str) -> str | None:
        """Identify which app a file belongs to."""
        normalized = filepath.removeprefix("backend/")
        for part in Path(normalized).parts:
            if part in self.apps:
                return part
        return None

    def _add(self, filepath: str, line: int, rule: str, message: str) -> None:
        self.violations.append(
            Violation(filepath=filepath, line=line, rule=rule, message=message)
        )

    def _check_engine_layout(
        self, filepath: str, path: Path, file_parts: tuple[str, ...]
    ) -> None:
        """Check engine layout (ENGINE-LAYOUT) and engine and module names (MODULE-NAME)."""
        if len(file_parts) < 2 or file_parts[0] != ENGINES_DIR:
            return
        engine = file_parts[1]

        if len(file_parts) == 3 and file_parts[2] == "__init__":
            if engine in LAYERS or engine in self.apps:
                self._add(
                    filepath,
                    1,
                    "MODULE-NAME",
                    f"Engine name '{engine}' clashes with a layer or app name.",
                )
            return

        if path.name == "apps.py":
            if len(file_parts) != 4:
                self._add(
                    filepath,
                    1,
                    "ENGINE-LAYOUT",
                    "apps.py must sit at engines/<engine>/<module>/apps.py.",
                )
                return
            module = file_parts[2]
            if module in LAYERS or module in self.apps:
                self._add(
                    filepath,
                    1,
                    "MODULE-NAME",
                    f"Module name '{module}' clashes with a layer or app name.",
                )
            return

        if len(file_parts) >= 4 and file_parts[2] not in LAYERS:
            module_dir = Path(*path.parts[: path.parts.index(ENGINES_DIR) + 3])
            if not (module_dir / "apps.py").exists():
                self._add(
                    filepath,
                    1,
                    "ENGINE-LAYOUT",
                    f"Module {module_dir} has no apps.py; it is not a Django app.",
                )

    def _check_module_boundary(
        self,
        filepath: str,
        line: int,
        file_parts: tuple[str, ...],
        targets: list[str],
    ) -> None:
        """Keep engine modules behind their services and dtos (CROSS-MODULE)."""
        source_engine, source_module, _ = _engine_position(file_parts)
        source = ".".join(file_parts)
        for target in targets:
            target_engine, target_module, head = _engine_position(target.split("."))
            if target_engine is None or (target_module is None and head is None):
                continue
            if target_module is None:
                # Engine-level code: only the engine service is public.
                if head == "services":
                    continue
                self._add(
                    filepath,
                    line,
                    "CROSS-MODULE",
                    f"Engine boundary: {source} imports {target}. "
                    f"Only engines.{target_engine}.services is public.",
                )
                continue
            if (target_engine, target_module) == (source_engine, source_module):
                continue
            if head == "dtos":
                continue
            # Module services are public inside their engine only; other
            # engines and plain apps go through engines.<engine>.services.
            if head == "services" and source_engine == target_engine:
                continue
            if head == "controllers" and _dotted_parts(filepath)[0] == COMPOSITION_ROOT:
                continue
            self._add(
                filepath,
                line,
                "CROSS-MODULE",
                f"Module boundary: {source} imports {target}. Only dtos cross "
                "module boundaries, and module services only inside their engine.",
            )

    def _check_import(
        self, filepath: str, line: int, from_layer: str | None, import_path: str
    ) -> None:
        """Check a single import for architecture violations."""
        if not from_layer:
            return

        if any(import_path.startswith(allowed) for allowed in ALLOWED_CROSS_IMPORTS):
            return

        target_layer = None
        import_parts = import_path.split(".")
        for part in import_parts:
            if part in LAYERS:
                target_layer = part
                break

        if not target_layer:
            return

        for forbidden_from, forbidden_to in FORBIDDEN_LAYER_DEPS:
            if from_layer == forbidden_from and target_layer == forbidden_to:
                self.violations.append(
                    Violation(
                        filepath=filepath,
                        line=line,
                        rule="LAYER-DEP",
                        message=(
                            f"Layer violation: {from_layer} -> {target_layer} "
                            f"(import {import_path}). "
                            f"{from_layer} must not depend on {target_layer}."
                        ),
                    )
                )

        from_app = self._identify_app(filepath)
        if from_layer == "controllers" and from_app:
            for part in import_parts:
                if part in self.apps and part != from_app:
                    if target_layer == "controllers":
                        self.violations.append(
                            Violation(
                                filepath=filepath,
                                line=line,
                                rule="CROSS-CTRL",
                                message=(
                                    f"Cross-app controller import: "
                                    f"{from_app}.controllers -> {part}.controllers "
                                    f"(import {import_path}). "
                                    f"Controllers should communicate via services."
                                ),
                            )
                        )
                    break

    def report(self) -> int:
        """Print results and return exit code."""
        if not self.violations:
            print(f"Architecture check passed ({self.files_checked} files checked)")
            return 0

        print(f"Architecture check FAILED ({len(self.violations)} violations):\n")
        for v in self.violations:
            print(f"  {v.filepath}:{v.line} [{v.rule}]")
            print(f"    {v.message}\n")
        return 1


def collect_python_files(paths: list[str] | None, check_all: bool) -> list[Path]:
    """Collect Python files to check."""
    if check_all or not paths:
        root = Path()
        apps = _detect_apps(root)
        # Also check backend/ for mattstack projects
        if (root / "backend").is_dir():
            apps |= _detect_apps(root / "backend")

        files: list[Path] = []
        # engines/ holds modules that are Django apps, not top-level apps.
        for app_name in [*sorted(apps), ENGINES_DIR]:
            for search_root in [root, root / "backend"]:
                app_dir = search_root / app_name
                if app_dir.exists():
                    files.extend(
                        f
                        for f in app_dir.rglob("*.py")
                        if not any(p in SKIP_DIRS for p in f.parts)
                    )
        return files

    return [Path(p) for p in paths if p.endswith(".py")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check architecture constraints")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument("--all", action="store_true", help="Check all app files")
    args = parser.parse_args()

    root = Path()
    apps = _detect_apps(root)
    if (root / "backend").is_dir():
        apps |= _detect_apps(root / "backend")

    files = collect_python_files(args.files, args.all)
    checker = ArchChecker(apps=apps)

    for f in files:
        if f.exists():
            checker.check_file(f)

    return checker.report()


if __name__ == "__main__":
    sys.exit(main())
