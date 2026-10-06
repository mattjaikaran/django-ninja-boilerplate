"""Example pgvector models: searchable documents and the links between them."""

import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from pgvector.django import HnswIndex, VectorField

from core.models.base import TimestampedModel

# The migration fixes the column size. Match the output size of
# AI_EMBEDDING_MODEL (1536 = OpenAI text-embedding-3-small); another size needs
# a new migration.
EMBEDDING_DIMENSIONS = 1536


class Document(TimestampedModel):
    """A text owned by one user, with a full-text search vector and an embedding.

    Every read path filters by ``owner``. Never return documents across users.
    """

    # ForeignKey adds a B-tree index on owner_id; read paths filter by it.
    owner: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_documents",
    )
    owner_id: uuid.UUID

    title: models.CharField = models.CharField(max_length=255)
    body: models.TextField = models.TextField()
    # Filled by the `embed_document` task after the row is saved.
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS, null=True, blank=True)
    # Postgres keeps this column in sync with title and body.
    search_vector = models.GeneratedField(
        expression=SearchVector("title", "body", config="english"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    class Meta:
        indexes = [
            # Cosine opclass: hybrid_search orders by CosineDistance.
            HnswIndex(
                name="ai_document_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
            GinIndex(name="ai_document_search_gin", fields=["search_vector"]),
        ]

    def __str__(self) -> str:
        return self.title


class DocumentLink(TimestampedModel):
    """A directed edge between two documents (graph_service walks these)."""

    source: models.ForeignKey = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="links_out"
    )
    target: models.ForeignKey = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="links_in"
    )
    # Attributes Django adds for the foreign keys (no django-stubs plugin).
    source_id: uuid.UUID
    target_id: uuid.UUID

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "target"], name="ai_documentlink_unique_edge"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_id} -> {self.target_id}"
