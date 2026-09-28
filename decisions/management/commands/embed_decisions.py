"""Compute Qwen3-Embedding vectors for decision fixtures.

Examples::

    python manage.py embed_decisions                 # fixtures without a vector
    python manage.py embed_decisions --force         # recompute every vector
    python manage.py embed_decisions --kind support_ticket
"""

from django.core.management.base import BaseCommand

from decisions.services import FixtureEmbeddingService


class Command(BaseCommand):
    """Fill ``DecisionFixture.embedding`` from the embeddings endpoint."""

    help = "Embed decision fixtures for similarity search"

    def add_arguments(self, parser) -> None:
        """Add command-line arguments."""
        parser.add_argument("--kind", help="Embed only this fixture kind")
        parser.add_argument(
            "--force", action="store_true", help="Recompute existing vectors"
        )

    def handle(self, *args, **options) -> None:
        """Embed the selected fixtures."""
        service = FixtureEmbeddingService()
        count = service.embed_fixtures(kind=options["kind"], force=options["force"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Embedded {count} decision fixtures with {service.model}"
            )
        )
