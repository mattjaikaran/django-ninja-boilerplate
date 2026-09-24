"""Regression tests for the settings modules.

``api.settings.prod`` used to raise ``NameError`` when ``ENVIRONMENT`` was
``development`` (the value shipped in ``.env.example``), because it mutated a
``CONTENT_SECURITY_POLICY`` object that ``common.py`` only defines outside
development. Production therefore loaded ``api.settings.dev`` silently.

Each module is exercised in a subprocess: Django caches settings per process,
so two settings modules cannot be imported in the same interpreter.

Run:
    uv run pytest tests/smoke/test_settings_modules.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Minimum environment the settings modules need in order to import.
BASE_ENV = {
    "SECRET_KEY": "settings-probe-secret",
    "DB_NAME": "probe",
    "DB_USER": "probe",
    "DB_PASSWORD": "probe",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
}

#: Printed on stdout as ``PROBE:<json>``; stdout also carries app log lines.
PROBE = """
import json

import django

django.setup()

from django.conf import settings

print("PROBE:" + json.dumps({
    "module": settings.SETTINGS_MODULE,
    "debug": settings.DEBUG,
    "hsts": getattr(settings, "SECURE_HSTS_SECONDS", None),
    "ssl_redirect": getattr(settings, "SECURE_SSL_REDIRECT", False),
    "use_tls": getattr(settings, "USE_TLS", None),
    "csp": bool(getattr(settings, "CONTENT_SECURITY_POLICY", None)),
    "csp_report_only": bool(
        getattr(settings, "CONTENT_SECURITY_POLICY_REPORT_ONLY", None)
    ),
    "session_cookie_age": getattr(settings, "SESSION_COOKIE_AGE", None),
    "rq_queues": getattr(settings, "RQ_QUEUES", None),
}))
"""


def probe(module: str, **overrides: str) -> dict:
    """Import *module* in a subprocess and return the settings it produced.

    Args:
        module: Dotted settings module to load.
        **overrides: Extra environment variables for the subprocess.

    Returns:
        The parsed probe payload.

    Raises:
        AssertionError: If the subprocess fails to import the module.
    """
    env = {**os.environ, **BASE_ENV, "DJANGO_SETTINGS_MODULE": module}
    # The selector falls back to dev when these are unset; keep them out of the
    # way so each test controls the environment explicitly.
    env.pop("DJANGO_ENVIRONMENT", None)
    env.pop("DJANGO_ENV", None)
    env.update(overrides)

    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        encoding="utf-8",
        env=env,
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode == 0, (
        f"{module} failed to import with "
        f"{overrides or 'no overrides'}:\n{result.stderr}"
    )

    payloads = [
        line.split("PROBE:", 1)[1]
        for line in result.stdout.splitlines()
        if "PROBE:" in line
    ]
    assert payloads, f"no probe output from {module}:\n{result.stdout}"
    return json.loads(payloads[-1])


@pytest.mark.smoke
class TestProductionSettings:
    """The production module must import and enforce its policy."""

    def test_imports_under_the_shipped_environment_default(self):
        data = probe("api.settings.prod", ENVIRONMENT="development")
        assert data["module"] == "api.settings.prod"

    def test_enforces_transport_security(self):
        data = probe("api.settings.prod", ENVIRONMENT="production", DEBUG="0")
        assert data["debug"] is False
        assert data["hsts"] == 31536000
        assert data["session_cookie_age"] == 3600

    def test_enforces_csp_without_a_report_only_duplicate(self):
        data = probe("api.settings.prod", ENVIRONMENT="development")
        assert data["csp"] is True
        assert data["csp_report_only"] is False

    def test_tls_redirect_is_opt_in(self):
        data = probe("api.settings.prod", ENVIRONMENT="production", DEBUG="0")
        assert data["use_tls"] is False
        assert data["ssl_redirect"] is False

    def test_tls_redirect_applies_when_enabled(self):
        data = probe(
            "api.settings.prod", ENVIRONMENT="production", DEBUG="0", USE_TLS="true"
        )
        assert data["ssl_redirect"] is True


@pytest.mark.smoke
class TestDevelopmentSettings:
    """Development stays permissive."""

    def test_uses_a_report_only_csp(self):
        data = probe("api.settings.dev", ENVIRONMENT="development")
        assert data["csp_report_only"] is True

    def test_does_not_enable_hsts(self):
        # Django defaults SECURE_HSTS_SECONDS to 0, which disables HSTS.
        data = probe("api.settings.dev", ENVIRONMENT="development")
        assert data["hsts"] == 0

    def test_normalizes_every_rq_queue_url(self):
        data = probe(
            "api.settings.dev",
            ENVIRONMENT="development",
            TASK_BACKEND="django_rq",
            REDIS_URL="valkey://localhost:6380/0",
        )
        assert {queue["URL"] for queue in data["rq_queues"].values()} == {
            "redis://localhost:6380/0"
        }

    def test_test_module_imports(self):
        assert probe("api.settings.test")["module"] == "api.settings.test"
