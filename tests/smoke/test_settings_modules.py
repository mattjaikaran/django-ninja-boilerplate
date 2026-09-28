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
    "CENTRIFUGO_TOKEN_SECRET": "settings-probe-realtime-secret",
    "NINJA_JWT_SIGNING_KEY": "settings-probe-jwt-signing-key",
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
    "hsts_include_subdomains": getattr(settings, "SECURE_HSTS_INCLUDE_SUBDOMAINS", False),
    "hsts_preload": getattr(settings, "SECURE_HSTS_PRELOAD", False),
    "ssl_redirect": getattr(settings, "SECURE_SSL_REDIRECT", False),
    "use_tls": getattr(settings, "USE_TLS", None),
    "csp": bool(getattr(settings, "CONTENT_SECURITY_POLICY", None)),
    "csp_report_only": bool(
        getattr(settings, "CONTENT_SECURITY_POLICY_REPORT_ONLY", None)
    ),
    "csp_directives": getattr(settings, "CONTENT_SECURITY_POLICY", {}).get(
        "DIRECTIVES", {}
    ),
    "session_cookie_age": getattr(settings, "SESSION_COOKIE_AGE", None),
    "session_cookie_secure": getattr(settings, "SESSION_COOKIE_SECURE", False),
    "csrf_cookie_secure": getattr(settings, "CSRF_COOKIE_SECURE", False),
    "proxy_ssl_header": getattr(settings, "SECURE_PROXY_SSL_HEADER", None),
    "referrer_policy": getattr(settings, "SECURE_REFERRER_POLICY", None),
    "allowed_hosts": getattr(settings, "ALLOWED_HOSTS", None),
    "rq_queues": getattr(settings, "RQ_QUEUES", None),
}))
"""


def _run_probe(
    module: str, drop: tuple[str, ...] = (), **overrides: str
) -> subprocess.CompletedProcess:
    """Run the PROBE subprocess for *module* without asserting success.

    Args:
        module: Dotted settings module to load.
        drop: Environment variable names to remove from the inherited copy
            (used to simulate a truly unset variable despite BASE_ENV).
        **overrides: Extra environment variables for the subprocess.

    Returns:
        The completed subprocess, so callers can assert on returncode/stderr.
    """
    env = {**os.environ, **BASE_ENV, "DJANGO_SETTINGS_MODULE": module}
    # The selector falls back to dev when these are unset; keep them out of the
    # way so each test controls the environment explicitly.
    env.pop("DJANGO_ENVIRONMENT", None)
    env.pop("DJANGO_ENV", None)
    for key in drop:
        env.pop(key, None)
    env.update(overrides)

    return subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        encoding="utf-8",
        env=env,
        cwd=PROJECT_ROOT,
        check=False,
    )


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
    result = _run_probe(module, **overrides)
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

    def test_enforces_transport_security_in_tls_mode(self):
        """When USE_TLS=true, full HSTS and session cookie age are enforced."""
        data = probe(
            "api.settings.prod", ENVIRONMENT="production", DEBUG="0", USE_TLS="true"
        )
        assert data["debug"] is False
        assert data["hsts"] == 31536000
        assert data["hsts_include_subdomains"] is True
        assert data["hsts_preload"] is True
        assert data["session_cookie_age"] == 3600
        assert data["session_cookie_secure"] is True
        assert data["csrf_cookie_secure"] is True

    def test_non_tls_deployment_disables_hsts(self):
        """Without USE_TLS, HSTS must be off — over HTTP it is ignored and
        SECURE_HSTS_PRELOAD is dangerous."""
        data = probe("api.settings.prod", ENVIRONMENT="production", DEBUG="0")
        assert data["hsts"] == 0
        assert data["hsts_include_subdomains"] is False
        assert data["hsts_preload"] is False

    def test_non_tls_deployment_keeps_cookies_and_proxy_header_off(self):
        """Plain-HTTP deployment must not set secure cookies or trust a proxy
        SSL header."""
        data = probe("api.settings.prod", ENVIRONMENT="production", DEBUG="0")
        assert data["session_cookie_secure"] is False
        assert data["csrf_cookie_secure"] is False
        assert data["proxy_ssl_header"] is None

    def test_tls_deployment_sets_proxy_header(self):
        """Behind a TLS-terminating proxy Django must trust
        X-Forwarded-Proto: https."""
        data = probe(
            "api.settings.prod", ENVIRONMENT="production", DEBUG="0", USE_TLS="true"
        )
        assert data["proxy_ssl_header"] == ["HTTP_X_FORWARDED_PROTO", "https"]

    def test_enforces_csp_without_a_report_only_duplicate(self):
        data = probe("api.settings.prod", ENVIRONMENT="development")
        assert data["csp"] is True
        assert data["csp_report_only"] is False

    def test_non_tls_deployment_omits_upgrade_insecure_requests(self):
        """Over plain HTTP, upgrade-insecure-requests would upgrade every
        subresource to a scheme the deployment does not serve."""
        data = probe("api.settings.prod", ENVIRONMENT="production", DEBUG="0")
        assert "upgrade-insecure-requests" not in data["csp_directives"]

    def test_tls_deployment_emits_upgrade_insecure_requests(self):
        """Over HTTPS, upgrade-insecure-requests upgrades legacy subresource
        references to https."""
        data = probe(
            "api.settings.prod", ENVIRONMENT="production", DEBUG="0", USE_TLS="true"
        )
        assert data["csp_directives"]["upgrade-insecure-requests"] is True

    def test_tls_redirect_is_opt_in(self):
        data = probe("api.settings.prod", ENVIRONMENT="production", DEBUG="0")
        assert data["use_tls"] is False
        assert data["ssl_redirect"] is False

    def test_tls_redirect_applies_when_enabled(self):
        data = probe(
            "api.settings.prod", ENVIRONMENT="production", DEBUG="0", USE_TLS="true"
        )
        assert data["ssl_redirect"] is True

    def test_rejects_the_development_realtime_secret(self):
        result = _run_probe(
            "api.settings.prod",
            ENVIRONMENT="production",
            CENTRIFUGO_TOKEN_SECRET="dev-centrifugo-token-secret",
        )
        assert result.returncode != 0
        assert "Set CENTRIFUGO_TOKEN_SECRET" in result.stderr

    def test_rejects_empty_secret_key(self):
        result = _run_probe(
            "api.settings.prod",
            ENVIRONMENT="production",
            SECRET_KEY="",
        )
        assert result.returncode != 0
        assert "SECRET_KEY" in result.stderr

    def test_rejects_missing_jwt_signing_key(self):
        result = _run_probe(
            "api.settings.prod",
            drop=("NINJA_JWT_SIGNING_KEY",),
            ENVIRONMENT="production",
        )
        assert result.returncode != 0
        assert "NINJA_JWT_SIGNING_KEY" in result.stderr

    def test_rejects_jwt_signing_key_equal_to_secret_key(self):
        result = _run_probe(
            "api.settings.prod",
            ENVIRONMENT="production",
            NINJA_JWT_SIGNING_KEY=BASE_ENV["SECRET_KEY"],
        )
        assert result.returncode != 0
        assert "NINJA_JWT_SIGNING_KEY" in result.stderr

    def test_debug_is_forced_off_even_when_env_says_true(self):
        """A development .env DEBUG=1 must never leak into a production load."""
        data = probe("api.settings.prod", ENVIRONMENT="production", DEBUG="1")
        assert data["debug"] is False

    def test_use_tls_lowercase_false_is_off(self):
        """The lowercase `false` shipped in .env.deploy.example must parse as
        off, never as a truthy redirect."""
        data = probe("api.settings.prod", ENVIRONMENT="production", USE_TLS="false")
        assert data["use_tls"] is False
        assert data["ssl_redirect"] is False
        assert data["hsts"] == 0

    def test_sets_strict_referrer_policy(self):
        data = probe("api.settings.prod", ENVIRONMENT="production")
        assert data["referrer_policy"] == "strict-origin-when-cross-origin"

    def test_allowed_hosts_defaults_to_reject_all(self):
        """An unset ALLOWED_HOSTS stays empty, so Django rejects every request
        (400 DisallowedHost) until the operator configures it — safe by default."""
        data = probe("api.settings.prod", ENVIRONMENT="production", ALLOWED_HOSTS="")
        assert data["allowed_hosts"] == []


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
