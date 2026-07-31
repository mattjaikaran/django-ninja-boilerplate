#!/usr/bin/env python3
"""Convention enforcer — catches AI anti-patterns the gauntlet misses.

Checks:
  1. DRF_IMPORT        — no rest_framework imports
  2. RAW_SCHEMA        — no raw ninja.Schema; must use CamelCaseSchema
  3. MODEL_SCHEMA      — no ninja.ModelSchema usage
  4. ROUTER_USAGE      — no ninja.Router function-based views
  5. DECORATOR_ORDER   — @http_* before @handle_exceptions
  6. MISSING_DECORATOR — write endpoints need @handle_exceptions
  7. UNSCOPED_QUERY    — no Model.objects.all() in controllers
  8. REDECLARED_FIELDS — no redeclared base model fields
  9. MISSING_EXPORTS   — __init__.py must export public classes
 10. PIP_USAGE         — no pip install in code/docs
 11. MOCKED_ORM        — no mocker.patch on ORM in tests
 12. CONTROLLER_REG    — controllers registered in api/urls.py

Usage:
    python scripts/check_conventions.py              # check all
    python scripts/check_conventions.py --check DRF_IMPORT  # single check
    python scripts/check_conventions.py --list       # list available checks
    python scripts/check_conventions.py --json       # JSON output

Exit: 0 = no violations, 1 = violations found
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".git",
    "__pycache__",
    "migrations",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "cli",
    "docs",
    ".context",
    "scripts",
}

# Fields that base models provide — must not be redeclared.
BASE_MODEL_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
    "is_active",
    "deleted_at",
    "deleted_by",
    "metadata",
}

# Maps each base class to the fields it provides (to avoid false positives)
BASE_CLASS_FIELDS: dict[str, set[str]] = {
    "TimestampedModel": {"id", "created_at", "updated_at"},
    "AuditBaseModel": {"id", "created_at", "updated_at", "created_by", "updated_by"},
    "SoftDeleteBaseModel": {
        "id",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "is_active",
        "deleted_at",
        "deleted_by",
        "metadata",
    },
    "SoftDeleteModel": {
        "id",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "is_active",
        "deleted_at",
        "deleted_by",
        "metadata",
    },
    "AbstractBaseModel": {
        "id",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "is_active",
        "deleted_at",
        "deleted_by",
        "metadata",
    },
}

# HTTP method decorators (must come before @handle_exceptions).
HTTP_METHOD_DECORATORS = {
    "http_get",
    "http_post",
    "http_put",
    "http_patch",
    "http_delete",
}

# Write HTTP methods that must have @handle_exceptions.
WRITE_METHODS = {"http_post", "http_put", "http_patch", "http_delete"}

# Directories whose __init__.py should export public classes.
EXPORT_DIRS = {"models", "schemas", "services", "controllers", "factories"}


@dataclass
class Violation:
    check: str
    filepath: str
    line: int
    message: str


@dataclass
class ConventionChecker:
    violations: list[Violation] = field(default_factory=list)
    check_names: set[str] | None = None
    _python_files: list[Path] = field(default_factory=list)

    def collect_files(self) -> list[Path]:
        if self._python_files:
            return self._python_files
        files: list[Path] = []
        for path in PROJECT_ROOT.rglob("*.py"):
            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue
            files.append(path)
        self._python_files = files
        return files

    def _controller_files(self) -> list[Path]:
        return [
            f
            for f in self.collect_files()
            if "controllers" in f.parts and f.name != "__init__.py"
        ]

    def _model_files(self) -> list[Path]:
        return [
            f
            for f in self.collect_files()
            if "models" in f.parts and f.name not in ("__init__.py", "base.py")
        ]

    def _schema_files(self) -> list[Path]:
        return [
            f
            for f in self.collect_files()
            if "schemas" in f.parts and f.name != "__init__.py"
        ]

    def _test_files(self) -> list[Path]:
        return [
            f
            for f in self.collect_files()
            if "tests" in f.parts and f.name.startswith("test_")
        ]

    def _init_files(self) -> list[Path]:
        return [
            f
            for f in self.collect_files()
            if f.name == "__init__.py" and any(d in f.parts for d in EXPORT_DIRS)
        ]

    # ── Check runners ────────────────────────────────────────────────────

    def check_drf_import(self) -> Iterator[Violation]:
        """No rest_framework imports anywhere."""
        for fpath in self.collect_files():
            text = fpath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(r"(from|import)\s+rest_framework", line):
                    yield Violation(
                        "DRF_IMPORT",
                        str(fpath.relative_to(PROJECT_ROOT)),
                        i,
                        "DRF import found — use Django Ninja Extra instead",
                    )

    def check_raw_schema(self) -> Iterator[Violation]:
        """No raw ninja.Schema — must use CamelCaseSchema from core.schemas.base_schema."""
        for fpath in self._schema_files():
            # Skip base_schema.py itself — it defines CamelCaseSchema
            if fpath.name == "base_schema.py":
                continue
            text = fpath.read_text()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue

            # Check imports: from ninja import Schema (without CamelCaseSchema)
            imports_camelcase = False
            imports_raw_schema = False
            schema_import_line = 0

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module == "ninja" or (
                        node.module and node.module.startswith("ninja")
                    ):
                        for alias in node.names:
                            if alias.name == "Schema":
                                imports_raw_schema = True
                                schema_import_line = node.lineno
                if isinstance(node, ast.ImportFrom):
                    if node.module == "core.schemas.base_schema":
                        for alias in node.names:
                            if alias.name == "CamelCaseSchema":
                                imports_camelcase = True

            if imports_raw_schema and not imports_camelcase:
                yield Violation(
                    "RAW_SCHEMA",
                    str(fpath.relative_to(PROJECT_ROOT)),
                    schema_import_line,
                    "Imports raw ninja.Schema — use CamelCaseSchema from core.schemas.base_schema",
                )

            # Check class definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "Schema":
                            if not imports_camelcase:
                                yield Violation(
                                    "RAW_SCHEMA",
                                    str(fpath.relative_to(PROJECT_ROOT)),
                                    node.lineno,
                                    f"Class {node.name} inherits raw Schema — use CamelCaseSchema",
                                )

    def check_model_schema(self) -> Iterator[Violation]:
        """No ninja.ModelSchema usage."""
        for fpath in self.collect_files():
            text = fpath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                # Match ModelSchema but not BaseModelSchema, ModelSchemaSomething
                if re.search(r"(?<![A-Za-z])ModelSchema(?![A-Za-z])", line):
                    if line.strip().startswith("#"):
                        continue
                    yield Violation(
                        "MODEL_SCHEMA",
                        str(fpath.relative_to(PROJECT_ROOT)),
                        i,
                        "ModelSchema usage — write explicit Pydantic schemas instead",
                    )

    def check_router_usage(self) -> Iterator[Violation]:
        """No ninja.Router function-based views."""
        for fpath in self.collect_files():
            text = fpath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(r"(from ninja import.*Router|Router\s*\()", line):
                    if line.strip().startswith("#"):
                        continue
                    yield Violation(
                        "ROUTER_USAGE",
                        str(fpath.relative_to(PROJECT_ROOT)),
                        i,
                        "ninja.Router usage — use @api_controller class-based controllers",
                    )

    def check_decorator_order(self) -> Iterator[Violation]:
        """@http_* decorators must come before @handle_exceptions."""
        for fpath in self._controller_files():
            text = fpath.read_text()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                decorator_names = [
                    (
                        d.func.id
                        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                        else d.id
                        if isinstance(d, ast.Name)
                        else None
                    )
                    for d in node.decorator_list
                ]
                decorator_names = [n for n in decorator_names if n is not None]

                http_idx = -1
                handle_exc_idx = -1
                for idx, name in enumerate(decorator_names):
                    if name in HTTP_METHOD_DECORATORS and http_idx == -1:
                        http_idx = idx
                    if name == "handle_exceptions" and handle_exc_idx == -1:
                        handle_exc_idx = idx

                if (
                    http_idx != -1
                    and handle_exc_idx != -1
                    and handle_exc_idx < http_idx
                ):
                    yield Violation(
                        "DECORATOR_ORDER",
                        str(fpath.relative_to(PROJECT_ROOT)),
                        node.lineno,
                        f"{node.name}: @handle_exceptions before @http_* — "
                        "@http_* must be outermost",
                    )

    def check_missing_decorator(self) -> Iterator[Violation]:
        """Write endpoints (POST/PUT/PATCH/DELETE) must have @handle_exceptions."""
        for fpath in self._controller_files():
            # Skip intentionally-basic controller patterns
            if fpath.stem.endswith("_basic") or fpath.stem.endswith("_declarative"):
                continue
            text = fpath.read_text()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                decorator_names = [
                    (
                        d.func.id
                        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                        else d.id
                        if isinstance(d, ast.Name)
                        else None
                    )
                    for d in node.decorator_list
                ]
                decorator_names = [n for n in decorator_names if n is not None]

                has_write_method = any(n in WRITE_METHODS for n in decorator_names)
                has_handle_exc = "handle_exceptions" in decorator_names

                if has_write_method and not has_handle_exc:
                    yield Violation(
                        "MISSING_DECORATOR",
                        str(fpath.relative_to(PROJECT_ROOT)),
                        node.lineno,
                        f"{node.name}: write endpoint missing @handle_exceptions()",
                    )

    def check_unscoped_query(self) -> Iterator[Violation]:
        """No Model.objects.all() in controller files."""
        for fpath in self._controller_files():
            text = fpath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(r"\.objects\.all\(\)", line):
                    if line.strip().startswith("#"):
                        continue
                    if "noqa:" in line:
                        continue
                    yield Violation(
                        "UNSCOPED_QUERY",
                        str(fpath.relative_to(PROJECT_ROOT)),
                        i,
                        ".objects.all() in controller — scope to request.user",
                    )

    def check_redeclared_fields(self) -> Iterator[Violation]:
        """No redeclaring base model fields (id, created_at, etc.)."""
        for fpath in self._model_files():
            text = fpath.read_text()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                # Only check classes that likely extend a base model
                for base in node.bases:
                    base_name = None
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr

                    if base_name in BASE_CLASS_FIELDS:
                        provided_fields = BASE_CLASS_FIELDS[base_name]
                        # Check class body for field assignments
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if (
                                        isinstance(target, ast.Name)
                                        and target.id in provided_fields
                                    ):
                                        yield Violation(
                                            "REDECLARED_FIELDS",
                                            str(fpath.relative_to(PROJECT_ROOT)),
                                            item.lineno,
                                            f"{node.name} redeclares '{target.id}' — "
                                            "provided by base model",
                                        )
                            elif isinstance(item, ast.AnnAssign):
                                if (
                                    isinstance(item.target, ast.Name)
                                    and item.target.id in provided_fields
                                ):
                                    yield Violation(
                                        "REDECLARED_FIELDS",
                                        str(fpath.relative_to(PROJECT_ROOT)),
                                        item.lineno,
                                        f"{node.name} redeclares '{item.target.id}' — "
                                        "provided by base model",
                                    )
                        break  # only check first matching base

    def check_missing_exports(self) -> Iterator[Violation]:
        """__init__.py in key dirs should export public classes."""
        for fpath in self._init_files():
            text = fpath.read_text()
            if not text.strip():
                continue  # empty is ok for some

            # If the directory has sibling .py files with classes, init should export
            parent = fpath.parent
            sibling_classes: list[str] = []
            for sf in parent.glob("*.py"):
                if sf.name == "__init__.py":
                    continue
                try:
                    tree = ast.parse(sf.read_text())
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                        name = node.name
                        # Skip Django/Pydantic inner classes that are never exported
                        if name in (
                            "Meta",
                            "Config",
                            "DoesNotExist",
                            "MultipleObjectsReturned",
                        ):
                            continue
                        sibling_classes.append(name)

            if not sibling_classes:
                continue

            has_all = "__all__" in text
            has_exports = all(cls_name in text for cls_name in sibling_classes)

            if not has_all or not has_exports:
                rel = str(fpath.relative_to(PROJECT_ROOT))
                missing = [c for c in sibling_classes if c not in text]
                yield Violation(
                    "MISSING_EXPORTS",
                    rel,
                    0,
                    f"Missing exports for: {', '.join(missing)}"
                    if missing
                    else "Missing __all__ — export public classes",
                )

    def check_pip_usage(self) -> Iterator[Violation]:
        """No pip install in Python files or shell scripts."""
        for fpath in self.collect_files():
            text = fpath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(r"pip\s+install", line):
                    if line.strip().startswith("#"):
                        continue
                    yield Violation(
                        "PIP_USAGE",
                        str(fpath.relative_to(PROJECT_ROOT)),
                        i,
                        "pip install found — use uv add instead",
                    )

        # Also check shell scripts and Makefile
        for pattern in ["*.sh", "Makefile"]:
            for fpath in PROJECT_ROOT.glob(pattern):
                if any(part in EXCLUDE_DIRS for part in fpath.parts):
                    continue
                text = fpath.read_text()
                for i, line in enumerate(text.splitlines(), 1):
                    if re.search(r"pip\s+install", line):
                        if line.strip().startswith("#"):
                            continue
                        yield Violation(
                            "PIP_USAGE",
                            str(fpath.relative_to(PROJECT_ROOT)),
                            i,
                            "pip install found — use uv add instead",
                        )

    def check_mocked_orm(self) -> Iterator[Violation]:
        """No mocker.patch on ORM calls in tests."""
        for fpath in self._test_files():
            text = fpath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(r'mocker\.patch\(["\'].*\.objects\.', line):
                    if line.strip().startswith("#"):
                        continue
                    yield Violation(
                        "MOCKED_ORM",
                        str(fpath.relative_to(PROJECT_ROOT)),
                        i,
                        "mocker.patch on ORM — test real database, don't mock",
                    )

    def check_controller_registration(self) -> Iterator[Violation]:
        """Every controller file should be registered in api/urls.py."""
        urls_path = PROJECT_ROOT / "api" / "urls.py"
        if not urls_path.exists():
            return

        urls_text = urls_path.read_text()

        for fpath in self._controller_files():
            text = fpath.read_text()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if this is a controller (has api_controller decorator)
                    is_controller = False
                    for dec in node.decorator_list:
                        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                            if dec.func.id == "api_controller":
                                is_controller = True
                                break

                    if is_controller and node.name not in urls_text:
                        yield Violation(
                            "CONTROLLER_REG",
                            str(fpath.relative_to(PROJECT_ROOT)),
                            node.lineno,
                            f"{node.name} not registered in api/urls.py",
                        )

    # ── Orchestration ────────────────────────────────────────────────────

    def run_all(self) -> int:
        checks_to_run = self.check_names or set(self.CHECKS.keys())  # type: ignore[attr-defined]
        for name, fn in self.CHECKS.items():  # type: ignore[attr-defined]
            if name not in checks_to_run:
                continue
            self.violations.extend(fn(self))
        return self.report()

    def report(self, *, json_output: bool = False) -> int:
        if json_output:
            print(
                json.dumps(
                    {
                        "violations": [
                            {
                                "check": v.check,
                                "file": v.filepath,
                                "line": v.line,
                                "message": v.message,
                            }
                            for v in self.violations
                        ],
                        "count": len(self.violations),
                    },
                    indent=2,
                )
            )
        else:
            if not self.violations:
                print("All convention checks passed.")
            for v in self.violations:
                print(f"[{v.check}] {v.filepath}:{v.line} — {v.message}")
            print(
                f"\n{violation_count} violation(s) found."
                if (violation_count := len(self.violations))
                else "\n0 violations."
            )
        return 1 if self.violations else 0


# Register checks
ConventionChecker.CHECKS = {  # type: ignore[attr-defined]
    "DRF_IMPORT": ConventionChecker.check_drf_import,
    "RAW_SCHEMA": ConventionChecker.check_raw_schema,
    "MODEL_SCHEMA": ConventionChecker.check_model_schema,
    "ROUTER_USAGE": ConventionChecker.check_router_usage,
    "DECORATOR_ORDER": ConventionChecker.check_decorator_order,
    "MISSING_DECORATOR": ConventionChecker.check_missing_decorator,
    "UNSCOPED_QUERY": ConventionChecker.check_unscoped_query,
    "REDECLARED_FIELDS": ConventionChecker.check_redeclared_fields,
    "MISSING_EXPORTS": ConventionChecker.check_missing_exports,
    "PIP_USAGE": ConventionChecker.check_pip_usage,
    "MOCKED_ORM": ConventionChecker.check_mocked_orm,
    "CONTROLLER_REG": ConventionChecker.check_controller_registration,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Django Ninja conventions")
    parser.add_argument("--check", type=str, help="Run a single check by name")
    parser.add_argument("--list", action="store_true", help="List available checks")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.list:
        for name in ConventionChecker.CHECKS:  # type: ignore[attr-defined]
            doc = ConventionChecker.CHECKS[name].__doc__ or ""  # type: ignore[attr-defined]
            print(f"  {name:<20} {doc.strip().split(chr(10))[0]}")
        return 0

    checker = ConventionChecker(
        check_names={args.check} if args.check else None,
    )
    result = checker.run_all()
    if args.json:
        checker.report(json_output=True)
    return result


if __name__ == "__main__":
    sys.exit(main())
