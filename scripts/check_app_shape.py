#!/usr/bin/env python3
"""Check API apps against the shared app shape contract.

An API app is a top-level directory with ``apps.py`` and a ``controllers/``
package. An engine module at ``engines/<engine>/<module>/`` with a
``controllers/`` package is an API app too.

Rules:

- APP-PACKAGE: ``models/``, ``schemas/``, ``services/``, ``controllers/`` and
  ``tests/`` exist. Each package that exists, including ``repositories/`` and
  ``dtos/``, has ``__init__.py``.
- APP-DEPENDENCY: ``dtos/`` requires ``repositories/``.
- APP-FILE: ``schemas/<name>_schema.py``, ``services/<name>_service.py``,
  ``repositories/<name>_repository.py``, ``dtos/<name>_dto.py`` and
  ``controllers/<name>_controller[_suffix].py``. Top-level ``tests/`` modules
  are ``test_*.py`` or ``conftest.py``.
- APP-CLASS: service, repository, DTO and controller modules define a class
  named ``<Name>Service``, ``<Name>Repository``, ``<Name>DTO`` or
  ``<Name>Controller*``. Matching ignores case and underscores.
- APP-EXEMPT: every ``EXEMPT`` path exists. A stale entry fails.

Exit 0 when every app passes. Exit 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PACKAGES = ("models", "schemas", "services", "controllers", "tests")
INIT_PACKAGES = (*REQUIRED_PACKAGES, "repositories", "dtos")

# package -> (module filename suffix, class suffix or None)
SUFFIX_RULES: dict[str, tuple[str, str | None]] = {
    "schemas": ("_schema", None),
    "services": ("_service", "service"),
    "repositories": ("_repository", "repository"),
    "dtos": ("_dto", "dto"),
}
CONTROLLER_RE = re.compile(
    r"^(?P<name>[a-z0-9]+(?:_[a-z0-9]+)*)_controller(?:_[a-z0-9]+)*$"
)

# Existing deviations. Key: repo-relative path. Remove an entry when the file
# is renamed or the class is renamed.
EXEMPT: dict[str, str] = {
    "billing/tests/urls.py": "URLconf for the test client, not a test module",
    "core/controllers/centrifugo_controller.py": (
        "class is CentrifugoTokenController, not CentrifugoController"
    ),
    "core/controllers/mixins.py": "shared controller mixin, not an endpoint module",
    "core/controllers/users_controller.py": (
        "class is UserController; module name is plural"
    ),
}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    message: str


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _norm(name: str) -> str:
    return name.replace("_", "").lower()


def discover_apps(root: Path) -> list[Path]:
    apps = [
        child
        for child in sorted(root.iterdir())
        if child.is_dir()
        and not child.name.startswith(".")
        and (child / "apps.py").is_file()
        and (child / "controllers").is_dir()
    ]
    engines = root / "engines"
    if engines.is_dir():
        for engine in sorted(engines.iterdir()):
            if engine.is_dir():
                apps.extend(
                    module
                    for module in sorted(engine.iterdir())
                    if module.is_dir() and (module / "controllers").is_dir()
                )
    return apps


def check_packages(app: Path) -> list[Violation]:
    violations: list[Violation] = []
    for pkg in REQUIRED_PACKAGES:
        if not (app / pkg).is_dir():
            violations.append(
                Violation(f"{_rel(app)}/{pkg}", 0, "APP-PACKAGE", f"missing {pkg}/")
            )
    for pkg in INIT_PACKAGES:
        package = app / pkg
        if package.is_dir() and not (package / "__init__.py").is_file():
            violations.append(
                Violation(
                    f"{_rel(app)}/{pkg}", 0, "APP-PACKAGE", f"{pkg}/ has no __init__.py"
                )
            )
    if (app / "dtos").is_dir() and not (app / "repositories").is_dir():
        violations.append(
            Violation(
                f"{_rel(app)}/dtos",
                0,
                "APP-DEPENDENCY",
                "dtos/ exists but repositories/ does not",
            )
        )
    return violations


def _check_class(
    module: Path, name: str, class_suffix: str, label: str, *, prefix: bool
) -> list[Violation]:
    rel = _rel(module)
    try:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=rel)
    except SyntaxError as exc:
        return [
            Violation(rel, exc.lineno or 1, "APP-PARSE", f"syntax error: {exc.msg}")
        ]
    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    want = _norm(name) + _norm(class_suffix)
    for cls in classes:
        got = _norm(cls)
        if got == want or (prefix and got.startswith(want)):
            return []
    found = ", ".join(classes) or "none"
    expected = "".join(part.capitalize() for part in name.split("_")) + label
    return [
        Violation(
            rel,
            1,
            "APP-CLASS",
            f"no class named {expected} (case and underscores ignored); "
            f"top-level classes: {found}",
        )
    ]


def _engine_of(module: Path) -> str | None:
    """Return the engine name when *module* sits in engines/<engine>/<module>/."""
    parts = module.resolve().relative_to(ROOT).parts
    if len(parts) > 3 and parts[0] == "engines":
        return parts[1]
    return None


def _check_module(module: Path, pkg: str) -> list[Violation]:
    rel = _rel(module)
    stem = module.stem
    if pkg == "tests":
        if stem.startswith("test_") or module.name == "conftest.py":
            return []
        return [Violation(rel, 0, "APP-FILE", "tests/ modules must be test_*.py")]
    if pkg == "controllers":
        match = CONTROLLER_RE.match(stem)
        if match is None:
            return [
                Violation(
                    rel,
                    0,
                    "APP-FILE",
                    "controllers/ modules must be <name>_controller[_suffix].py",
                )
            ]
        name = match.group("name")
        found = _check_class(module, name, "controller", "Controller*", prefix=True)
        engine = _engine_of(module)
        if found and engine:
            # Engine controllers are <Engine><Model>Controller so operation ids
            # stay unique across engines.
            return _check_class(
                module, f"{engine}_{name}", "controller", "Controller*", prefix=True
            )
        return found
    suffix, class_suffix = SUFFIX_RULES[pkg]
    if not stem.endswith(suffix):
        return [
            Violation(rel, 0, "APP-FILE", f"{pkg}/ modules must end in {suffix}.py")
        ]
    if class_suffix is None:
        return []
    labels = {"service": "Service", "repository": "Repository", "dto": "DTO"}
    return _check_class(
        module, stem[: -len(suffix)], class_suffix, labels[class_suffix], prefix=False
    )


def check_modules(app: Path) -> list[Violation]:
    violations: list[Violation] = []
    for pkg in ("tests", "controllers", *SUFFIX_RULES):
        package = app / pkg
        if not package.is_dir():
            continue
        for module in sorted(package.glob("*.py")):
            if module.name != "__init__.py":
                violations.extend(_check_module(module, pkg))
    return violations


def check_app(app: Path) -> list[Violation]:
    found = check_packages(app) + check_modules(app)
    return [v for v in found if v.path not in EXEMPT]


def check_exempt() -> list[Violation]:
    return [
        Violation(path, 0, "APP-EXEMPT", "EXEMPT entry no longer exists; remove it")
        for path in EXEMPT
        if not (ROOT / path).exists()
    ]


def _owns(app: Path, changed: Path) -> bool:
    return changed == app or app in changed.parents


def report(checked: int, violations: list[Violation]) -> int:
    if not violations:
        print(f"App shape check passed ({checked} apps checked)")
        return 0
    print(f"App shape check FAILED ({len(violations)} violations):")
    for v in violations:
        location = f"{v.path}:{v.line}" if v.line else v.path
        print(f"  {location} [{v.rule}]")
        print(f"    {v.message}")
        print()
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", help="Changed files; checks their apps")
    parser.add_argument("--all", action="store_true", help="Check every API app")
    args = parser.parse_args(argv)

    apps = discover_apps(ROOT)
    if args.files and not args.all:
        changed = [Path(f).resolve() for f in args.files]
        apps = [app for app in apps if any(_owns(app, c) for c in changed)]

    violations = [v for app in apps for v in check_app(app)]
    violations.extend(check_exempt())
    return report(len(apps), violations)


if __name__ == "__main__":
    sys.exit(main())
