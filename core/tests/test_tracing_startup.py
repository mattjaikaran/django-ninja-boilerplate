"""CoreConfig starts OpenTelemetry only when OTEL_ENABLED is true."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from core.apps import CoreConfig


@pytest.fixture
def calls(monkeypatch):
    seen: list[str] = []

    def fake_init() -> bool:
        seen.append("init")
        return True

    monkeypatch.setattr("core.observability.tracing.init_tracing", fake_init)
    monkeypatch.setattr(
        "core.observability.tracing.instrument_all", lambda: seen.append("instrument")
    )
    return seen


def test_disabled_does_not_start_tracing(settings, calls):
    settings.OTEL_ENABLED = False
    CoreConfig._init_tracing()
    assert calls == []


def test_enabled_starts_and_instruments(settings, calls):
    settings.OTEL_ENABLED = True
    CoreConfig._init_tracing()
    assert calls == ["init", "instrument"]


def test_enabled_without_packages_fails_loud(settings, monkeypatch):
    settings.OTEL_ENABLED = True
    monkeypatch.setattr("core.observability.tracing.init_tracing", lambda: False)
    with pytest.raises(ImproperlyConfigured, match="observability"):
        CoreConfig._init_tracing()
