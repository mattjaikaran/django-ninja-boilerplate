"""Dramatiq worker bootstrap that initializes Django before consuming tasks."""

import os
from importlib import import_module

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")
django.setup()

_execute = import_module("api.tasks.backends.dramatiq_backend")._execute

__all__ = ["_execute"]
