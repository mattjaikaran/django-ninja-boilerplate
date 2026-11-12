"""Test settings ignore local environment values that must not leak in.

Covers two contracts: test tokens stay usable when local signing keys are
blank or unrelated, and each optional app installs and mounts its routes only
when its flag is set.
"""

import json
import os
import subprocess
import sys

import pytest

#: (env flag, app label, one route the app registers when installed)
OPTIONAL_APPS = [
    ("ORGANIZATIONS_ENABLED", "organizations", "/api/organizations/"),
    ("NOTIFICATIONS_ENABLED", "notifications", "/api/notifications/"),
    ("BILLING_ENABLED", "billing", "/api/billing/plans"),
]

SETTINGS_PROBE = """
import json

import django

django.setup()

from django.conf import settings
from api.urls import api

print("PROBE:" + json.dumps({
    "installed_apps": list(settings.INSTALLED_APPS),
    "paths": sorted(api.get_openapi_schema()["paths"]),
}))
"""


def optional_app_env(**overrides: str) -> dict[str, str]:
    """Environment for a clean settings probe: no inherited optional flags."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "api.settings.test",
        "DJANGO_READ_DOT_ENV": "0",
    }
    for flag, _app, _route in OPTIONAL_APPS:
        env.pop(flag, None)
    env.pop("TODOS_ENABLED", None)
    env.update(overrides)
    return env


def probe_optional_apps(**overrides: str) -> dict[str, list[str]]:
    result = subprocess.run(
        [sys.executable, "-c", SETTINGS_PROBE],
        env=optional_app_env(**overrides),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    line = next(
        line
        for line in reversed(result.stdout.splitlines())
        if line.startswith("PROBE:")
    )
    return json.loads(line.removeprefix("PROBE:"))


@pytest.fixture(scope="module")
def default_optional_apps() -> dict[str, list[str]]:
    return probe_optional_apps()


@pytest.mark.parametrize("local_signing_key", ["", "unrelated-local-signing-key"])
def test_access_tokens_ignore_local_environment_keys(local_signing_key: str) -> None:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "api.settings.test",
        "NINJA_JWT_SIGNING_KEY": local_signing_key,
        "ENVIRONMENT": "development",
        "DJANGO_ENVIRONMENT": "development",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import json
import django
import jwt

django.setup()
from django.conf import settings
from ninja_jwt.tokens import AccessToken

encoded = str(AccessToken())
restored = AccessToken(encoded)
try:
    jwt.decode(encoded, settings.SECRET_KEY, algorithms=["HS256"])
except jwt.InvalidSignatureError:
    django_key_accepted = False
else:
    django_key_accepted = True
print(json.dumps({"token_type": restored["token_type"], "django_key_accepted": django_key_accepted}))
""",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert json.loads(result.stdout.splitlines()[-1]) == {
        "token_type": "access",
        "django_key_accepted": False,
    }


@pytest.mark.parametrize(("flag", "app", "route"), OPTIONAL_APPS)
def test_optional_app_follows_its_flag(
    flag: str,
    app: str,
    route: str,
    default_optional_apps: dict[str, list[str]],
) -> None:
    assert app not in default_optional_apps["installed_apps"]
    assert route not in default_optional_apps["paths"]

    enabled = probe_optional_apps(**{flag: "true"})
    assert app in enabled["installed_apps"]
    assert route in enabled["paths"]


def test_todos_is_on_by_default(default_optional_apps: dict[str, list[str]]) -> None:
    assert "todos" in default_optional_apps["installed_apps"]
    assert "/api/todos/" in default_optional_apps["paths"]


def test_todos_flag_removes_app_and_routes() -> None:
    disabled = probe_optional_apps(TODOS_ENABLED="false")
    assert "todos" not in disabled["installed_apps"]
    assert "/api/todos/" not in disabled["paths"]


def test_disabled_todos_tests_skip_instead_of_error() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "todos", "-q", "-p", "no:cacheprovider"],
        env=optional_app_env(TODOS_ENABLED="false"),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode in (0, 5), output
    assert "error" not in output.lower(), output


def test_disabled_optional_app_tests_skip_instead_of_error() -> None:
    """`pytest <app>` used to fail collection while the app was off."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *(app for _flag, app, _route in OPTIONAL_APPS),
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        env=optional_app_env(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = result.stdout + result.stderr
    # pytest exits 5 when every collected module is skipped, 0 when another
    # test in the run passed. A collection error exits 2.
    assert result.returncode in (0, 5), output
    assert "skipped" in output.lower(), output
    assert "error" not in output.lower(), output
