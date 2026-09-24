"""Load decision fixtures from ``decisions/data/fixtures``.

The command is idempotent: re-running it updates existing fixtures in place.
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from decisions.services import DecisionService

#: Directory holding the ``*.json`` fixture files.
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures"


class Command(BaseCommand):
    """Seed the ``DecisionFixture`` table from JSON files."""

    help = "Load decision fixtures from decisions/data/fixtures into the database"

    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        parser.add_argument(
            "--dir",
            default=str(FIXTURES_DIR),
            help="Directory holding the fixture JSON files",
        )

    def handle(self, *args, **options) -> None:
        """Load every fixture file in the target directory."""
        fixtures_dir = Path(options["dir"])
        if not fixtures_dir.is_dir():
            self.stderr.write(f"Fixture directory not found: {fixtures_dir}")
            return

        counts = DecisionService().seed_fixtures(fixtures_dir)
        self.stdout.write(
            self.style.SUCCESS(
                f"Decision fixtures seeded: {counts['created']} created, "
                f"{counts['updated']} updated"
            )
        )
