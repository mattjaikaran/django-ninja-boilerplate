"""Stored decision fixtures.

A fixture is a named example payload for the decision engine. Fixtures give
the dev seed command something to load and give retrieval work a corpus to
search.

``embedding`` is a native pgvector ``vector`` column, filled by
``FixtureEmbeddingService`` (``manage.py embed_decisions``). Postgres needs the
``vector`` extension, which the initial migration creates on PostgreSQL only;
SQLite accepts the column type, so the test suite runs unchanged.
"""

from django.db import models
from pgvector.django import VectorField

from core.models import AbstractBaseModel

#: Width of the embedding vectors: the output size of Qwen3-Embedding-0.6B, the
#: default ``DECISION_EMBEDDING_MODEL``. A different model must match it.
EMBEDDING_DIMENSIONS = 1024

#: Fixture categories. Each maps to one seed file in ``data/fixtures``.
FIXTURE_KINDS = [
    ("support_ticket", "Support ticket"),
    ("form_submission", "Form submission"),
    ("api_payload", "API payload"),
]


class DecisionFixture(AbstractBaseModel):
    """A named example payload for the decision engine."""

    kind = models.CharField(max_length=32, choices=FIXTURE_KINDS)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    payload = models.JSONField(default=dict)
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.kind}:{self.name}"

    class Meta:
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "name"], name="unique_fixture_kind_name"
            )
        ]
        verbose_name = "Decision fixture"
        verbose_name_plural = "Decision fixtures"
