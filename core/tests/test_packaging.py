"""Keep the Hatch wheel in step with the installed Django apps."""

import tomllib
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

ROOT = Path(settings.BASE_DIR)

PYPROJECT = """\
[project]
name = "demo"

[tool.hatch.build.targets.wheel]
packages = ["api", "core"]
"""


def test_wheel_packages_every_local_installed_app():
    """A local app missing from the wheel breaks ``django.setup()`` on install."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    packages = set(pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])
    local_apps = {
        app.split(".")[0]
        for app in settings.INSTALLED_APPS
        if (ROOT / app.split(".")[0] / "__init__.py").is_file()
    }
    assert local_apps
    assert local_apps - packages == set()


def _wheel_packages(tmp_path):
    pyproject = tomllib.loads((tmp_path / "pyproject.toml").read_text())
    return pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]


def test_startapp_extended_adds_the_new_app_to_the_wheel(tmp_path, monkeypatch):
    """A generated app outside the wheel breaks ``django.setup()`` on install."""
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    monkeypatch.chdir(tmp_path)

    call_command("startapp_extended", "gadget")

    assert _wheel_packages(tmp_path) == ["api", "core", "gadget"]


@pytest.mark.parametrize(
    "packages",
    [
        'packages = [\n  "api",\n  "core"\n]',
        'packages = ["api", "core",]',
    ],
)
def test_startapp_extended_keeps_the_wheel_list_valid(tmp_path, monkeypatch, packages):
    """Any valid list shape must gain a comma before the new entry."""
    (tmp_path / "pyproject.toml").write_text(
        f"[tool.hatch.build.targets.wheel]\n{packages}\n"
    )
    monkeypatch.chdir(tmp_path)

    call_command("startapp_extended", "gadget")

    assert _wheel_packages(tmp_path) == ["api", "core", "gadget"]
