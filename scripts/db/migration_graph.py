"""Read Django migration files without importing Django.

Shared by check_migrations.py and renumber_migrations.py. Everything here
parses source text with `ast`; nothing executes a migration.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

PATH_RE = re.compile(
    r"^(?P<dir>(?:[\w.\-]+/)*migrations)/(?P<num>\d{4})_(?P<rest>\w+)\.py$"
)
NAME_RE = re.compile(r"^(?P<num>\d{4})_(?P<rest>\w+)$")
PAIR_RE = re.compile(
    r"""\(\s*(?P<q1>['"])(?P<app>[\w.]+)(?P=q1)\s*,\s*(?P<q2>['"])(?P<name>\w+)(?P=q2)\s*\)"""
)
# Operations that need a human when an own migration contains them.
RISKY_OPS = frozenset(
    {"RunPython", "RunSQL", "RemoveField", "RenameField", "DeleteModel"}
)
FIELD_OPS = frozenset({"AddField", "AlterField", "RemoveField", "RenameField"})


class MigrationParseError(Exception):
    """A migration file is not understood well enough to rewrite it."""


@dataclass
class Info:
    """What a renumber or a check needs to know about one migration file."""

    deps: list[tuple[str, str]] = field(default_factory=list)
    operations: list[str] = field(
        default_factory=list
    )  # every Call name inside operations
    touched: set[tuple[str, str | None]] = field(
        default_factory=set
    )  # (model, field|None)
    alters: set[tuple[str, str]] = field(
        default_factory=set
    )  # (model, field) of AlterField
    replaces: bool = False


def number(name: str) -> int:
    m = NAME_RE.match(name)
    if not m:
        raise MigrationParseError(f"{name}: not a numbered migration name")
    return int(m["num"])


def _str(node: ast.expr | None) -> str | None:
    return (
        node.value
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        else None
    )


def _arg(call: ast.Call, index: int, keyword: str) -> str | None:
    for kw in call.keywords:
        if kw.arg == keyword:
            return _str(kw.value)
    return _str(call.args[index]) if len(call.args) > index else None


def _call_name(call: ast.Call) -> str:
    f = call.func
    return (
        f.attr
        if isinstance(f, ast.Attribute)
        else f.id
        if isinstance(f, ast.Name)
        else ""
    )


def parse(text: str, path: str) -> Info:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise MigrationParseError(f"{path}: {exc}") from exc
    classes = [
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Migration"
    ]
    if len(classes) != 1:
        raise MigrationParseError(f"{path}: expected one Migration class")
    info = Info()
    seen: set[str] = set()
    for stmt in classes[0].body:
        if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id in ("operations", "dependencies"):
                raise MigrationParseError(
                    f"{path}: `{stmt.target.id} +=` is not readable"
                )
        targets = (
            [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if isinstance(stmt, ast.Assign)
            else [stmt.target.id]
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            else []
        )
        value = getattr(stmt, "value", None)
        if "replaces" in targets:
            info.replaces = True
        for name in ("dependencies", "operations"):
            if name not in targets:
                continue
            if name in seen or not isinstance(value, (ast.List, ast.Tuple)):
                # A reference, a call or a second assignment: refuse, never guess.
                raise MigrationParseError(f"{path}: `{name}` is not one list literal")
            seen.add(name)
            if name == "dependencies":
                for el in value.elts:
                    if isinstance(el, ast.Tuple) and len(el.elts) == 2:
                        app, dep = _str(el.elts[0]), _str(el.elts[1])
                        if app and dep:
                            info.deps.append((app, dep))
            else:
                _scan_ops(value, info)
    if seen != {"dependencies", "operations"}:
        raise MigrationParseError(
            f"{path}: needs `dependencies` and `operations` lists"
        )
    return info


def _scan_ops(value: ast.expr, info: Info) -> None:
    for node in ast.walk(value):
        if not isinstance(node, ast.Call):
            continue
        kind = _call_name(node)
        info.operations.append(kind)
        if kind in FIELD_OPS:
            model = (_arg(node, 0, "model_name") or "").lower()
            names = (
                [_arg(node, 1, "old_name"), _arg(node, 2, "new_name")]
                if kind == "RenameField"
                else [_arg(node, 1, "name")]
            )
            for name in names:
                info.touched.add((model, name))
                if kind == "AlterField" and name:
                    info.alters.add((model, name))
        elif kind in {"CreateModel", "DeleteModel", "RenameModel", "AlterModelTable"}:
            info.touched.add(((_arg(node, 0, "name") or "").lower(), None))


def dir_label(directory: str, infos: dict[str, Info]) -> str:
    """The app label of a migrations directory: the folder name unless the
    migrations name their siblings under another label."""
    folder = directory.split("/")[-2] if "/" in directory else ""
    seen: dict[str, int] = {}
    for name, info in infos.items():
        for app, dep in info.deps:
            if dep in infos and dep < name:
                seen[app] = seen.get(app, 0) + 1
    if not seen or folder in seen:
        return folder
    return max(seen, key=lambda k: seen[k])


def app_deps(info: Info, label: str, known: set[str] | dict[str, Info]) -> list[str]:
    """Names this migration lists in dependencies for its own app."""
    return [dep for app, dep in info.deps if app == label and dep in known]


def leaves(infos: dict[str, Info], label: str) -> list[str]:
    """Migrations of one app that no other migration of it depends on."""
    referenced: set[str] = set()
    for info in infos.values():
        referenced.update(app_deps(info, label, infos))
    return sorted(n for n in infos if n not in referenced)


def ancestors(infos: dict[str, Info], label: str, start: str) -> set[str]:
    """`start` and every migration of the app it depends on, transitively."""
    seen: set[str] = set()
    todo = [start]
    while todo:
        cur = todo.pop()
        if cur in seen or cur not in infos:
            continue
        seen.add(cur)
        todo.extend(app_deps(infos[cur], label, infos))
    return seen
