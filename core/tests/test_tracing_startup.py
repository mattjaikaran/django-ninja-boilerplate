"""CoreConfig fails loud when OTEL_ENABLED is true but tracing cannot start."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from core.apps import CoreConfig


def test_enabled_without_packages_fails_loud(settings, monkeypatch):
    settings.OTEL_ENABLED = True
    monkeypatch.setattr("core.observability.tracing.init_tracing", lambda: False)
    with pytest.raises(ImproperlyConfigured, match="observability"):
        CoreConfig._init_tracing()
