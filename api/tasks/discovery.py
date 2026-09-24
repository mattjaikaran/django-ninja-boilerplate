"""Discover task modules after Django finishes loading applications."""

from importlib import import_module

from django.apps import apps
from django.utils.module_loading import module_has_submodule


def autodiscover_tasks() -> None:
    """Import each installed application's task module when present."""
    for app_config in apps.get_app_configs():
        if module_has_submodule(app_config.module, "tasks"):
            import_module(f"{app_config.name}.tasks")


__all__ = ["autodiscover_tasks"]
