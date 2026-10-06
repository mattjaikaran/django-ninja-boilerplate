"""Load the project's own secret generator, scripts/env_secrets.py.

The list of generated secrets lives in that file only, so the CLI imports it
from the project it creates or sets up instead of keeping a copy.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path("scripts") / "env_secrets.py"


def load_env_secrets(project_root: Path) -> ModuleType:
    """Import ``scripts/env_secrets.py`` from ``project_root``."""
    path = project_root / SCRIPT
    spec = importlib.util.spec_from_file_location("project_env_secrets", path)
    if spec is None or spec.loader is None or not path.exists():
        raise FileNotFoundError(f"Secret generator not found: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_project_env(
    project_root: Path,
    overrides: dict[str, str] | None = None,
) -> list[str]:
    """Write ``project_root/.env`` with generated secrets; return their names.

    Raises FileNotFoundError when the project has no ``scripts/env_secrets.py``
    and FileExistsError when ``.env`` exists.
    """
    module = load_env_secrets(project_root)
    template = project_root / module.TEMPLATE_FILE
    names: list[str] = module.create_env(
        project_root / module.ENV_FILE,
        template if template.exists() else None,
        overrides,
    )
    return names
