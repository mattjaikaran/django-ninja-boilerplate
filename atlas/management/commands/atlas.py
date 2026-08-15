"""Management command: generate the codebase atlas data file.

Usage::

    python manage.py atlas                      # write atlas-data.json
    python manage.py atlas --output /tmp/a.json # custom path
    python manage.py atlas --no-samples         # skip audit-log mining

The admin page regenerates lazily on first view; run this command to
refresh the data after code changes without waiting for the cache TTL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from atlas.services.atlas_service import generate_atlas


class Command(BaseCommand):
    """Generate the codebase atlas data file for the admin map."""

    help = "Generate the codebase atlas data file for the admin map."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--output",
            default=None,
            help="Path to write the JSON data (default: settings.ATLAS_DATA_PATH)",
        )
        parser.add_argument(
            "--no-samples",
            action="store_true",
            help="Skip real request samples from the audit log",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        default_path = Path(settings.BASE_DIR) / "atlas-data.json"
        output = Path(
            options["output"] or getattr(settings, "ATLAS_DATA_PATH", default_path)
        )
        data = generate_atlas(include_real_samples=not options["no_samples"])
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

        meta = data["meta"]
        self.stdout.write(self.style.SUCCESS(f"Atlas written to {output}"))
        self.stdout.write(
            f"  {meta['app_count']} apps, {meta['endpoint_count']} endpoints, "
            f"{meta['model_count']} models, {meta['total_loc']} LOC"
        )
