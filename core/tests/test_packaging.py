"""Keep the Hatch wheel in step with the installed Django apps."""

import tomllib
from pathlib import Path

from django.conf import settings

ROOT = Path(settings.BASE_DIR)


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
