#!/usr/bin/env python3
"""Renumber the branch's own Django migrations after main's latest.

Policy: migrations are linearized, never merged. NEVER run
`makemigrations --merge`. Two branches that each add 0004 in one app are
fixed by moving the later branch's files to 0005, 0006, ... after main's
latest and pointing their dependencies at main's leaf.

Steps (a dry run unless --apply):
  1. fetch origin main.
  2. Own files: migration files added against the base (committed `A`,
     staged `A` and untracked). A file already on the base is never touched.
  3. Per app with own files: main's latest number and leaf. A collision is an
     own number at or below main's latest, or an own first migration that does
     not depend on main's leaf.
  4. Refuse (exit 4, `escalate to owner`) when an own migration of a colliding
     app has RunPython, RunSQL, RemoveField, RenameField, DeleteModel,
     `replaces` (a squash), or an AlterField on a field that main's concurrent
     migrations touch.
  5. Rename each own file to the next free number, rewrite its `dependencies`
     (own first migration -> main's leaf; any own migration, in any app, that
     named a renamed own migration -> the new name).
  6. --apply then verifies: `makemigrations --check --dry-run`, then a real
     `migrate` on a throwaway Postgres container (--skip-migrate to skip).

Usage:
    python3 scripts/db/renumber_migrations.py [--apply] [--commit] [--base origin/main]
                                              [--no-fetch] [--skip-verify] [--skip-migrate]

Exit: 0 nothing to do or applied and verified, 3 dry run found a collision,
4 escalate to owner, 1 verification failed, 2 usage or git error.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from migration_graph import (
    PAIR_RE,
    PATH_RE,
    RISKY_OPS,
    Info,
    MigrationParseError,
    ancestors,
    app_deps,
    dir_label,
    leaves,
    number,
    parse,
)  # fmt: skip
from renumber_apply import (
    COMMIT_MESSAGE,
    ROOT,
    apply_moves,
    commit_moves,
    git,
    rollback,
    verify,
)

COLLIDES, ESCALATE = 3, 4


class Escalate(Exception):
    """The renumber is not safe to do by script."""


def own_files(base: str) -> list[str]:
    """Migration paths the branch adds against base."""
    found = set(
        git(
            "diff", "--name-only", "--no-renames", "--diff-filter=A", f"{base}...HEAD"
        ).split()
    )
    found |= set(
        git("diff", "--name-only", "--no-renames", "--diff-filter=A", "HEAD").split()
    )
    found |= set(git("ls-files", "-o", "--exclude-standard").split())
    on_base = set(git("ls-tree", "-r", "--name-only", base).split())
    return sorted(p for p in found if PATH_RE.match(p) and p not in on_base)


def base_infos(base: str, directory: str) -> dict[str, Info]:
    names = [
        p
        for p in git("ls-tree", "--name-only", base, f"{directory}/").split()
        if PATH_RE.match(p)
    ]
    return {Path(p).stem: parse(git("show", f"{base}:{p}"), p) for p in names}


@dataclass
class Plan:
    """What to do for one migrations directory."""

    directory: str
    label: str
    why: str
    leaf: str
    renames: dict[str, str] = field(default_factory=dict)  # old name -> new name
    root: str = ""
    old_parent: str = ""


def plan_dir(base: str, directory: str, own: dict[str, str]) -> Plan | None:
    """A Plan when the own migrations of `directory` collide with base, else None."""
    on_base = base_infos(base, directory)
    if not on_base:
        return None  # a new app cannot collide
    infos = {n: parse(t, f"{directory}/{n}.py") for n, t in own.items()}
    label = dir_label(directory, {**on_base, **infos})
    main_leaves = leaves(on_base, label)
    if len(main_leaves) != 1:
        raise Escalate(
            f"{directory}: main has {len(main_leaves)} latest migrations {main_leaves}"
        )
    leaf, top = main_leaves[0], max(number(n) for n in on_base)
    roots = [n for n, i in infos.items() if not app_deps(i, label, infos)]
    if len(roots) != 1:
        raise Escalate(
            f"{directory}: the own migrations have {len(roots)} starting points {roots}"
        )
    root = roots[0]
    parents = app_deps(infos[root], label, on_base)
    lowest = min(number(n) for n in infos)
    if lowest <= top:
        why = f"own migration {lowest:04d} is at or below main's latest {top:04d}"
    elif parents != [leaf]:
        why = f"own {root} does not depend on main's latest {leaf}"
    else:
        return None
    if len(parents) != 1:
        raise Escalate(
            f"{directory}: own {root} has {len(parents)} in-app parents {parents}"
        )
    plan = Plan(directory, label, why, leaf, root=root, old_parent=parents[0])
    _refuse_risky(plan, on_base, infos)
    order: list[str] = []
    while len(order) < len(infos):
        step = sorted(
            (
                n
                for n in infos
                if n not in order
                and set(app_deps(infos[n], label, infos)) <= set(order)
            ),
            key=lambda n: (number(n), n),
        )
        if not step:
            raise Escalate(
                f"{directory}: the own migrations depend on each other in a cycle"
            )
        order.append(step[0])
    for i, name in enumerate(order, start=top + 1):
        plan.renames[name] = f"{i:04d}_{name.split('_', 1)[1]}"
    return plan


def _refuse_risky(plan: Plan, on_base: dict[str, Info], infos: dict[str, Info]) -> None:
    concurrent = set(on_base) - ancestors(on_base, plan.label, plan.old_parent)
    touched = (
        set().union(*(on_base[n].touched for n in concurrent)) if concurrent else set()
    )
    for name, info in sorted(infos.items()):
        if info.replaces:
            raise Escalate(
                f"{plan.directory}/{name}.py is a squashed migration (replaces)"
            )
        risky = sorted(RISKY_OPS & set(info.operations))
        if risky:
            raise Escalate(f"{plan.directory}/{name}.py contains {', '.join(risky)}")
        for model, fld in sorted(info.alters):
            if (model, fld) in touched or (model, None) in touched:
                raise Escalate(
                    f"{plan.directory}/{name}.py alters {model}.{fld}, which main's "
                    f"concurrent migrations ({', '.join(sorted(concurrent))}) also touch"
                )


def rewrite(
    text: str,
    renames: dict[tuple[str, str], str],
    parent: tuple[tuple[str, str], str] | None,
) -> str:
    """Swap dependency pairs: renames maps (label, old) -> new name; `parent`
    ((label, old), new) applies to this file only (the own first migration)."""

    def swap(m: re.Match[str]) -> str:
        key = (m["app"], m["name"])
        new = parent[1] if parent and key == parent[0] else renames.get(key)
        if new is None:
            return m[0]
        return f"({m['q1']}{m['app']}{m['q1']}, {m['q2']}{new}{m['q2']})"

    return PAIR_RE.sub(swap, text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--apply", action="store_true", help="write the renames (default: dry run)"
    )
    ap.add_argument(
        "--commit", action="store_true", help=f'with --apply: commit "{COMMIT_MESSAGE}"'
    )
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--skip-verify", action="store_true")
    ap.add_argument(
        "--skip-migrate",
        action="store_true",
        help="verify without the scratch-DB migrate",
    )
    args = ap.parse_args()

    if not args.no_fetch and args.base.startswith("origin/"):
        git("fetch", "-q", "origin", args.base.split("/", 1)[1])
    if subprocess.run(
        ["git", "rev-parse", "--verify", "-q", args.base],
        cwd=ROOT,
        capture_output=True,
        check=False,
    ).returncode:
        print(f"renumber: base {args.base} does not resolve")
        return 2

    by_dir: dict[str, dict[str, str]] = {}
    texts: dict[str, str] = {}
    paths = own_files(args.base)
    for p in paths:
        m = PATH_RE.match(p)
        texts[p] = (ROOT / p).read_text(encoding="utf-8")
        by_dir.setdefault(m["dir"], {})[Path(p).stem] = texts[p]
    try:
        for p in paths:
            try:
                squash = parse(texts[p], p).replaces
            except MigrationParseError:
                continue  # plan_dir refuses an unreadable file of a colliding app
            if squash:
                raise Escalate(f"{p} is a squashed migration (replaces)")
        plans = [
            pl
            for d, own in sorted(by_dir.items())
            if (pl := plan_dir(args.base, d, own))
        ]
    except (Escalate, MigrationParseError) as exc:
        print(f"renumber: refused: {exc}\nescalate to owner")
        return ESCALATE
    if not plans:
        print(
            f"renumber: no migration collides with {args.base} ({len(paths)} own file(s))"
        )
        return 0

    global_map = {
        (pl.label, old): new for pl in plans for old, new in pl.renames.items()
    }
    moves: dict[str, tuple[str, str]] = {}  # old path -> (new path, new text)
    for pl in plans:
        print(f"COLLISION {pl.directory}: {pl.why}")
        for old, new in pl.renames.items():
            print(f"  rename {old}.py -> {new}.py")
        print(f"  {pl.root} now depends on main's {pl.leaf} (was {pl.old_parent})")
    for p in paths:
        m = PATH_RE.match(p)
        pl = next((x for x in plans if x.directory == m["dir"]), None)
        stem = Path(p).stem
        parent = (
            ((pl.label, pl.old_parent), pl.leaf) if pl and stem == pl.root else None
        )
        new_text = rewrite(texts[p], global_map, parent)
        new_path = (
            f"{m['dir']}/{pl.renames[stem]}.py" if pl and stem in pl.renames else p
        )
        if new_text != texts[p] or new_path != p:
            moves[p] = (new_path, new_text)
            if new_text != texts[p] and new_path == p:
                print(f"  rewrite dependencies in {p}")
    if not args.apply:
        print("dry run: re-run with --apply to write")
        return COLLIDES

    tracked = apply_moves(moves)
    # Verify before the commit. A failure puts every file and the index back
    # as they were: exit 1 leaves the tree exactly as it found it.
    status = 0 if args.skip_verify else verify(args.skip_migrate)
    if status != 0:
        rollback(moves, texts, tracked)
        print("renumber: verification failed; the renames are undone")
    elif args.commit:
        commit_moves(moves)
    return status


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())
