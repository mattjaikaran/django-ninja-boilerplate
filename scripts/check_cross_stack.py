#!/usr/bin/env python3
"""Cross-stack convention enforcer for fullstack (backend/ + frontend/) monorepos.

Checks conventions that span both stacks:
  1. NAMING_CONSISTENCY — model names match across stacks
  2. SCHEMA_PARITY       — backend schemas have frontend type equivalents
  3. TOOLING_CONSISTENCY — consistent tooling (uv/bun, ruff/eslint)
  4. RULES_CONSISTENCY   — both stacks have .omp/ convention rules
  5. GAUNTLET_CONSISTENCY — both stacks have gauntlet gates configured

Usage:
    python scripts/check_cross_stack.py                    # auto-detect monorepo
    python scripts/check_cross_stack.py --root /path/to/monorepo
    python scripts/check_cross_stack.py --backend ./backend --frontend ./frontend

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


@dataclass
class Violation:
    check: str
    filepath: str
    line: int
    message: str


@dataclass
class CrossStackChecker:
    violations: list[Violation] = field(default_factory=list)
    backend_root: Path | None = None
    frontend_root: Path | None = None

    def detect_roots(self, root: Path) -> bool:
        """Auto-detect backend/ and frontend/ in a monorepo root."""
        backend = root / "backend"
        frontend = root / "frontend"

        if backend.is_dir() and frontend.is_dir():
            self.backend_root = backend
            self.frontend_root = frontend
            return True

        # Also check if we're running inside backend/ of a monorepo
        parent = root.parent
        if parent.name == "backend" and (parent.parent / "frontend").is_dir():
            self.backend_root = root
            self.frontend_root = parent.parent / "frontend"
            return True

        # Or running inside frontend/
        if parent.name == "frontend" and (parent.parent / "backend").is_dir():
            self.frontend_root = root
            self.backend_root = parent.parent / "backend"
            return True

        return False

    def check_naming_consistency(self) -> Iterator[Violation]:
        """Backend model names should map cleanly to frontend type names."""
        if not self.backend_root or not self.frontend_root:
            return

        # Collect backend model names
        backend_models: set[str] = set()
        models_dir = self.backend_root
        for py_file in models_dir.rglob("models/*.py"):
            if py_file.name in {"__init__.py", "base.py"}:
                continue
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Heuristic: model classes have Meta or fields
                    has_meta = any(
                        isinstance(item, ast.ClassDef) and item.name == "Meta"
                        for item in node.body
                    )
                    has_fields = any(
                        isinstance(item, (ast.Assign, ast.AnnAssign))
                        for item in node.body
                    )
                    if (has_meta or has_fields) and not node.name.startswith("_"):
                        backend_models.add(node.name)

        # Collect frontend type names
        frontend_types: set[str] = set()
        types_dir = self.frontend_root / "src" / "types"
        if types_dir.is_dir():
            for ts_file in types_dir.rglob("*.ts"):
                text = ts_file.read_text()
                for match in re.finditer(
                    r"(?:export\s+)?(?:interface|type)\s+(\w+)", text
                ):
                    frontend_types.add(match.group(1))

        # Check for mismatches
        # Backend: PascalCase models (Todo, UserProfile)
        # Frontend: same names as types (Todo, UserProfile)

        # Common transpositions: backend User -> frontend User (ok)
        # Issue: backend model exists but no frontend type
        # This is a warning, not an error — not all models need frontend types

        # Check for naming convention drift: frontend types should mirror backend
        for model in sorted(backend_models):
            # Skip internal/Django models
            if model in (
                "AbstractBaseModel",
                "SoftDeleteModel",
                "SoftDeleteBaseModel",
                "TimestampedModel",
                "AuditBaseModel",
                "BaseModel",
                "AuditLog",
                "FeatureFlag",
                "APIKey",
                "User",
            ):
                continue
            if model not in frontend_types:
                rel_path = self.backend_root
                yield Violation(
                    "NAMING_CONSISTENCY",
                    f"backend model: {model}",
                    0,
                    f"No matching frontend type found for {model} — "
                    "create type in src/types/",
                )

    def check_schema_parity(self) -> Iterator[Violation]:
        """Every backend CamelCaseSchema should have a frontend type equivalent."""
        if not self.backend_root or not self.frontend_root:
            return

        # Collect backend schemas
        backend_schemas: dict[str, Path] = {}
        for py_file in self.backend_root.rglob("schemas/*.py"):
            if py_file.name == "__init__.py":
                continue
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        base_name = None
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            base_name = base.attr
                        if base_name in (
                            "CamelCaseSchema",
                            "Schema",
                            "BaseModelSchema",
                        ):
                            if "Schema" in node.name and not node.name.startswith("_"):
                                backend_schemas[node.name] = py_file

        # Collect frontend types
        frontend_text = ""
        types_dir = self.frontend_root / "src" / "types"
        if types_dir.is_dir():
            for ts_file in types_dir.rglob("*.ts"):
                frontend_text += ts_file.read_text() + "\n"

        for schema_name, schema_path in sorted(backend_schemas.items()):
            # Map schema name to expected frontend type
            # TodoSchema → Todo, CreateTodoSchema might not have frontend type
            if schema_name.endswith("Schema"):
                type_name = schema_name[:-6]  # strip "Schema"
                # Skip request schemas (Create*, Update*)
                if type_name.startswith(("Create", "Update")):
                    continue
                if type_name not in frontend_text:
                    rel = schema_path.relative_to(self.backend_root)
                    yield Violation(
                        "SCHEMA_PARITY",
                        str(rel),
                        0,
                        f"Schema {schema_name} has no matching frontend type {type_name}",
                    )

    def check_tooling_consistency(self) -> Iterator[Violation]:
        """Both stacks should use consistent tooling."""
        if not self.backend_root or not self.frontend_root:
            return

        # Check package managers
        be_pyproject = self.backend_root / "pyproject.toml"
        fe_package = self.frontend_root / "package.json"

        if be_pyproject.exists():
            be_text = be_pyproject.read_text()
            if "pip" in be_text and "uv" not in be_text:
                yield Violation(
                    "TOOLING_CONSISTENCY",
                    str(be_pyproject.relative_to(PROJECT_ROOT)),
                    0,
                    "Backend uses pip — should use uv for consistency",
                )

        if fe_package.exists():
            fe_text = fe_package.read_text()
            if re.search(r'"(npm|yarn)"', fe_text) and "bun" not in fe_text:
                yield Violation(
                    "TOOLING_CONSISTENCY",
                    str(fe_package.relative_to(PROJECT_ROOT)),
                    0,
                    "Frontend uses npm/yarn — should use bun for consistency",
                )

    def check_rules_consistency(self) -> Iterator[Violation]:
        """Both stacks should have .omp/ convention rules."""
        if not self.backend_root or not self.frontend_root:
            return

        be_rules = self.backend_root / ".omp" / "rules"
        fe_rules = self.frontend_root / ".omp" / "rules"

        if not be_rules.is_dir() or not any(be_rules.iterdir()):
            yield Violation(
                "RULES_CONSISTENCY",
                str(
                    (self.backend_root / ".omp").relative_to(PROJECT_ROOT)
                    if self.backend_root
                    else ""
                ),
                0,
                "Backend missing .omp/rules/ — add convention rules",
            )

        if not fe_rules.is_dir() or not any(fe_rules.iterdir()):
            yield Violation(
                "RULES_CONSISTENCY",
                str(
                    (self.frontend_root / ".omp").relative_to(PROJECT_ROOT)
                    if self.frontend_root
                    else ""
                ),
                0,
                "Frontend missing .omp/rules/ — add convention rules",
            )

    def check_gauntlet_consistency(self) -> Iterator[Violation]:
        """Both stacks should have gauntlet gates configured."""
        if not self.backend_root or not self.frontend_root:
            return

        # Check backend has gauntlet
        be_gauntlet = self.backend_root / "scripts" / "gauntlet.py"
        be_makefile = self.backend_root / "Makefile"

        has_be_gauntlet = be_gauntlet.exists()
        if not has_be_gauntlet and be_makefile.exists():
            has_be_gauntlet = "gauntlet" in be_makefile.read_text()

        # Check frontend has gauntlet
        fe_package = self.frontend_root / "package.json"
        has_fe_gauntlet = False
        if fe_package.exists():
            has_fe_gauntlet = "gauntlet" in fe_package.read_text()

        if not has_be_gauntlet:
            yield Violation(
                "GAUNTLET_CONSISTENCY",
                str(self.backend_root),
                0,
                "Backend missing gauntlet — add gauntlet.py + Makefile targets",
            )

        if not has_fe_gauntlet:
            yield Violation(
                "GAUNTLET_CONSISTENCY",
                str(self.frontend_root),
                0,
                "Frontend missing gauntlet — add gauntlet:quick script to package.json",
            )

    def run_all(self) -> int:
        for fn in self.CHECKS.values():  # type: ignore[attr-defined]
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
                print("All cross-stack checks passed.")
            for v in self.violations:
                print(f"[{v.check}] {v.filepath}:{v.line} — {v.message}")
            count = len(self.violations)
            print(f"\n{count} violation(s) found." if count else "\n0 violations.")
        return 1 if self.violations else 0


CrossStackChecker.CHECKS = {  # type: ignore[attr-defined]
    "NAMING_CONSISTENCY": CrossStackChecker.check_naming_consistency,
    "SCHEMA_PARITY": CrossStackChecker.check_schema_parity,
    "TOOLING_CONSISTENCY": CrossStackChecker.check_tooling_consistency,
    "RULES_CONSISTENCY": CrossStackChecker.check_rules_consistency,
    "GAUNTLET_CONSISTENCY": CrossStackChecker.check_gauntlet_consistency,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-stack convention checker")
    parser.add_argument("--root", type=str, help="Monorepo root path")
    parser.add_argument("--backend", type=str, help="Backend path")
    parser.add_argument("--frontend", type=str, help="Frontend path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    checker = CrossStackChecker()

    if args.backend and args.frontend:
        checker.backend_root = Path(args.backend)
        checker.frontend_root = Path(args.frontend)
    elif args.root:
        checker.detect_roots(Path(args.root))
    else:
        # Auto-detect: try current dir, then parent
        if not checker.detect_roots(PROJECT_ROOT):
            checker.detect_roots(PROJECT_ROOT.parent)
        if not checker.backend_root or not checker.frontend_root:
            print("Could not detect monorepo structure (backend/ + frontend/).")
            print("Run with --backend and --frontend flags, or from a monorepo root.")
            return 1

    print(f"Backend:  {checker.backend_root}")
    print(f"Frontend: {checker.frontend_root}")
    print()

    result = checker.run_all()
    if args.json:
        checker.report(json_output=True)
    return result


if __name__ == "__main__":
    sys.exit(main())
