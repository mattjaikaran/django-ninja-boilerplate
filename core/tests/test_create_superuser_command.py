"""Regression tests for the create_superuser management command.

The command must fail with a non-zero exit code (CommandError) for every
failure: missing variables, a refused password and a validation error. Only
an existing superuser is a success.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import User

pytestmark = pytest.mark.django_db

SUPERUSER_ENV = {
    "SUPERUSER_EMAIL": "admin@example.com",
    "SUPERUSER_USERNAME": "admin",
    "SUPERUSER_PASSWORD": "a-long-development-password",
    "SUPERUSER_FIRST_NAME": "Admin",
    "SUPERUSER_LAST_NAME": "User",
}


@pytest.fixture
def superuser_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    for name, value in SUPERUSER_ENV.items():
        monkeypatch.setenv(name, value)
    return SUPERUSER_ENV


@pytest.mark.parametrize("missing", sorted(SUPERUSER_ENV))
def test_missing_variable_raises_command_error(superuser_env, monkeypatch, missing):
    monkeypatch.delenv(missing)

    with pytest.raises(CommandError, match=missing):
        call_command("create_superuser")

    assert not User.objects.exists()


def test_refused_password_outside_development_raises_command_error(
    superuser_env, monkeypatch
):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SUPERUSER_PASSWORD", "short")

    with pytest.raises(CommandError, match="SUPERUSER_PASSWORD"):
        call_command("create_superuser")

    assert not User.objects.exists()


def test_creates_superuser_and_reports_the_email_login(superuser_env):
    out = StringIO()

    call_command("create_superuser", stdout=out)

    user = User.objects.get(email="admin@example.com")
    assert user.is_superuser is True
    assert user.check_password(SUPERUSER_ENV["SUPERUSER_PASSWORD"]) is True
    assert "Log in with email: admin@example.com" in out.getvalue()


def test_existing_email_is_reported_without_an_error(superuser_env):
    User.objects.create_superuser(
        email="admin@example.com",
        username="previous-admin",
        password="another-long-password",
    )
    out = StringIO()

    call_command("create_superuser", stdout=out)

    assert User.objects.count() == 1
    assert "Superuser 'admin@example.com' already exists." in out.getvalue()


def test_user_manager_validation_error_raises_command_error(superuser_env):
    User.objects.create_superuser(
        email="someone-else@example.com",
        username="admin",
        password="another-long-password",
    )

    with pytest.raises(CommandError, match="Could not create superuser"):
        call_command("create_superuser")

    assert User.objects.count() == 1
