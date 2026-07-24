#!/usr/bin/env python3
"""Architecture enforcement for the Django Ninja Boilerplate.

Validates layered architecture constraints:
  Controllers → Services → Models (no skipping layers, no reverse deps)

Also detects cross-app controller coupling and enforces module boundaries.

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
    "controllers": 3,
    "schemas": 2,
    "services": 2,
    "tasks": 2,
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
    "api.pagination",
    "api.throttling",
    "api.decorators",
    "api.tasks",
}

FORBIDDEN_LAYER_DEPS = [
    ("models", "controllers"),
    ("models", "services"),
    ("models", "schemas"),
    ("services", "controllers"),
    ("migrations", "controllers"),
    ("migrations", "services"),
    ("migrations", "schemas"),
]

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

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_import(relative, node.lineno, from_layer, alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                self._check_import(relative, node.lineno, from_layer, node.module)

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
        for app_name in sorted(apps):
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
