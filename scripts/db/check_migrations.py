#!/usr/bin/env python3
"""Migration checks for the pre-commit hook, the pre-push hook, the gauntlet
MIGRATIONS gate and CI. Policy: migrations are linearized, never merged.

Three checks, each with its own failure message:

  no-merge    static, no Django. Fails on a migration file with "merge" in its
              name, on a merge-only migration (`operations = []` and two
              dependencies in one app), and on an inline
              `# safe-migrations: ignore` comment (rule exceptions live in
              api/settings/migration_lint.py only).
  leaf        `makemigrations --check --dry-run`: fails on several leaf nodes
              in one app (a conflict: run scripts/db/renumber_migrations.py)
              or on model changes without a migration.
  lint        django-safe-migrations on the migrations the branch changes
              against the base (`check_migrations --diff origin/main`). Fails
              on ERROR. Its SM027 (several leaf migrations) is a conflict too.

Usage:
    python3 scripts/db/check_migrations.py [--base origin/main] [--only no-merge,leaf,lint] [--staged]

Exit: 0 pass, 1 a check failed. Needs `uv sync --extra dev` for leaf and lint.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from migration_graph import MigrationParseError, parse

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT
BASELINE = ROOT / "scripts" / "baselines" / "migration-safety.json"
SETTINGS = "api.settings.migration_lint"
# Env that points the settings at a real Postgres (renumber_apply.py scratch migrate).
SCRATCH_ENV = {"TEST_DB": "postgres"}
RENUMBER = "python3 scripts/db/renumber_migrations.py"
INLINE_IGNORE_RE = re.compile(r"#\s*safe-migrations\s*:\s*ignore", re.IGNORECASE)
CONFLICT_HELP = (
    "A migration conflict is fixed by renumbering, never by a merge migration.\n"
    "  NEVER run `makemigrations --merge`.\n"
    f"  1. `just migrations-renumber` (dry run: {RENUMBER}) shows the plan.\n"
    f"  2. `just migrations-renumber --apply` (or `{RENUMBER} --apply`) renames your\n"
    "     own migration files after main's latest, re-checks and migrates a scratch DB.\n"
    "  3. It prints `escalate to owner` for RunPython, RunSQL, RemoveField, RenameField,\n"
    "     DeleteModel or a clashing AlterField: stop and ask the owner."
)


def migration_files() -> list[Path]:
    return sorted(
        p
        for p in BACKEND.glob("**/migrations/[0-9]*.py")
        if ".venv" not in p.parts and "node_modules" not in p.parts
    )


def check_no_merge(files: list[Path] | None = None) -> list[str]:
    """Return one message per violation."""
    problems: list[str] = []
    for path in files if files is not None else migration_files():
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        if "merge" in path.name.lower():
            problems.append(
                f"{rel}: a migration file with 'merge' in its name is banned"
            )
        if INLINE_IGNORE_RE.search(text):
            problems.append(
                f"{rel}: inline `# safe-migrations: ignore` is banned; "
                "add the rule exception to SAFE_MIGRATIONS in api/settings/migration_lint.py"
            )
        try:
            info = parse(text, str(rel))
            tree = ast.parse(text)
        except (MigrationParseError, SyntaxError):
            continue
        empty = _operations_empty(tree)
        same_app = [
            app for app, n in Counter(a for a, _ in info.deps).items() if n >= 2
        ]
        if empty and same_app:
            problems.append(
                f"{rel}: a merge-only migration (operations = [] with two dependencies in "
                f"'{same_app[0]}') is banned"
            )
    return problems


def _operations_empty(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Migration":
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "operations"
                        for t in stmt.targets
                    )
                    and isinstance(stmt.value, (ast.List, ast.Tuple))
                    and not stmt.value.elts
                ):
                    return True
    return False


def django_env() -> dict[str, str]:
    env = dict(os.environ)
    env["DJANGO_SETTINGS_MODULE"] = SETTINGS
    for key, value in {
        "SECRET_KEY": "migration-check-only",  # pragma: allowlist secret
        "DB_NAME": "test_db",
        "DB_USER": "postgres",
        "DB_PASSWORD": "postgres",  # pragma: allowlist secret
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "5432",
    }.items():
        env.setdefault(key, value)
    return env


def manage(
    *args: str, env: dict[str, str] | None = None, timeout: int | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--extra", "dev", "python", "manage.py", *args],
        cwd=BACKEND, env=env or django_env(), capture_output=True, text=True,
        check=False, timeout=timeout,
    )  # fmt: skip


def _no_merge_hint(text: str) -> str:
    """Drop the lines of a tool's output that tell the reader to merge."""
    return "\n".join(ln for ln in text.splitlines() if "--merge" not in ln)


def check_leaf(env: dict[str, str] | None = None) -> list[str]:
    proc = manage("makemigrations", "--check", "--dry-run", env=env)
    if proc.returncode == 0:
        return []
    out = proc.stdout + proc.stderr
    if "onflicting migrations" in out:
        leaf = [
            ln.strip()
            for ln in out.splitlines()
            if "leaf node" in ln or "in the migration graph" in ln
        ]
        return [
            f"conflicting migrations (several leaf nodes): {' '.join(leaf)}\n{CONFLICT_HELP}"
        ]
    if "No changes" not in out and "Migrations for" in out:
        return [
            "model changes without a migration. Run `python manage.py makemigrations`, "
            "commit the file.\n" + _no_merge_hint(out)[-1500:]
        ]
    return [f"makemigrations --check failed:\n{_no_merge_hint(out)[-2500:]}"]


def check_lint(base: str) -> list[str]:
    args = ["check_migrations", "--diff", base, "--format=github", "--no-suggestions"]
    if BASELINE.is_file():
        args += ["--baseline", str(BASELINE)]
    proc = manage(*args)
    if proc.returncode == 0:
        return []
    out = proc.stdout + proc.stderr
    if "SM027" in out or "leaf migrations" in out:
        return [
            f"django-safe-migrations SM027: several leaf migrations (a conflict)\n{CONFLICT_HELP}"
        ]
    return [
        f"django-safe-migrations found ERROR issues:\n{_no_merge_hint(out)[-4000:]}"
    ]


MODEL_RE = re.compile(r"(^|/)migrations/[^/]+\.py$|(^|/)models(/[^/]+)?\.py$|/models/")


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    return out.stdout.split()


def touches_migrations(files: list[str]) -> bool:
    return any(f.startswith("") and MODEL_RE.search(f) for f in files)


def resolve_base(base: str) -> str:
    """Make sure `base` resolves: a shallow CI checkout lacks origin/main."""

    def ok() -> bool:
        return (
            subprocess.run(
                ["git", "rev-parse", "--verify", "-q", base],
                cwd=ROOT,
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )

    if not ok() and base.startswith("origin/"):
        remote, _, branch = base.partition("/")
        subprocess.run(
            ["git", "fetch", "-q", remote, branch],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
    if not ok():
        sys.exit(f"check_migrations: base {base} does not resolve; fetch it first")
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    parser.add_argument(
        "--only", default="no-merge,leaf,lint", help="comma list of checks"
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="pre-commit: no-merge always; leaf and lint only when a staged path is a "
        "migration or a model",
    )
    args = parser.parse_args()
    wanted = set(args.only.split(","))
    if args.staged and not touches_migrations(staged_files()):
        wanted = {"no-merge"}
    failures: list[tuple[str, list[str]]] = []

    if "no-merge" in wanted:
        problems = check_no_merge()
        print(f"  {'FAIL' if problems else 'ok  '}  no-merge")
        if problems:
            failures.append(("no-merge", problems))
    slow = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        if "leaf" in wanted:
            slow["leaf"] = pool.submit(check_leaf)
        if "lint" in wanted:
            base = resolve_base(args.base)
            slow["lint"] = pool.submit(check_lint, base)
        for name, fut in slow.items():
            problems = fut.result()
            print(f"  {'FAIL' if problems else 'ok  '}  {name}")
            if problems:
                failures.append((name, problems))
    for name, problems in failures:
        print(f"\n[{name}]")
        print("\n".join(problems))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
