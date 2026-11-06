"""Settings for the migration checks (dev extra only).

`makemigrations --check --dry-run` and `check_migrations` (django-safe-migrations)
need no database. scripts/db/check_migrations.py and CI select this module;
the production image never installs the dev extra, so it never imports it.
"""

from .test import *
from .test import INSTALLED_APPS as _TEST_APPS

INSTALLED_APPS = [*_TEST_APPS, "django_safe_migrations"]

# The one place for django-safe-migrations rule exceptions. Inline
# `# safe-migrations: ignore` comments are banned (scripts/db/check_migrations.py).
# Existing findings sit in scripts/baselines/migration-safety.json. Keep a
# rule exception here short, with the reason beside it.
SAFE_MIGRATIONS: dict[str, object] = {
    "DISABLED_RULES": [],
}
