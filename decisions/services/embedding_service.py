"""Embed decision fixtures and find the stored examples nearest to a case.

The service calls an OpenAI-compatible ``/v1/embeddings`` endpoint. The
default model is Qwen3-Embedding-0.6B, served by the ``embeddings`` Compose
profile (llama.cpp) or by ``just embedder-local`` on the host. Vectors live in
the pgvector ``DecisionFixture.embedding`` column, and similarity is cosine
distance computed by Postgres.

Qwen3-Embedding is instruction-aware: a query carries a one-line task
instruction, and stored documents do not.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, cast

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pgvector.django import CosineDistance

from api.exceptions import ExternalServiceError
from decisions.models import DecisionFixture
from decisions.models.decision_fixture import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

#: Texts sent per embeddings request.
BATCH_SIZE = 32


def render(value: Any, indent: int = 0) -> str:
    """Render a JSON value as ``key: value`` prose, which embeds better than JSON."""
    pad = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}{key}:\n{render(item, indent + 2)}")
            else:
                lines.append(f"{pad}{key}: {render(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        return "\n".join(f"{pad}- {render(item, indent + 2).strip()}" for item in value)
    if value is None:
        return ""
    return str(value)


def fixture_text(fixture: DecisionFixture) -> str:
    """Return the document text embedded for *fixture*."""
    parts = [fixture.description.strip(), render(fixture.payload)]
    return "\n\n".join(part for part in parts if part)


class FixtureEmbeddingService:
    """Compute fixture embeddings and run nearest-neighbour search."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        instruction: str | None = None,
    ) -> None:
        """Read unset options from the ``DECISION_EMBEDDING_*`` settings."""
        self._client = client
        self.url = url if url is not None else settings.DECISION_EMBEDDING_URL
        self.model = model or settings.DECISION_EMBEDDING_MODEL
        self.api_key = (
            api_key if api_key is not None else settings.DECISION_EMBEDDING_API_KEY
        )
        self.instruction = (
            instruction
            if instruction is not None
            else settings.DECISION_EMBEDDING_INSTRUCTION
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per text, in order.

        Raises:
            ImproperlyConfigured: If no endpoint is configured, it is
                unreachable, or it returns vectors of the wrong width.
            ExternalServiceError: If the endpoint answers with an error.
        """
        if not self.url:
            raise ImproperlyConfigured(
                "DECISION_EMBEDDING_URL is empty. Start the `embeddings` Compose "
                "profile or `just embedder-local`, then set the URL."
            )
        if self._client is None:
            self._client = httpx.Client(timeout=120.0)
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = list(texts[start : start + BATCH_SIZE])
            try:
                response = self._client.post(
                    self.url,
                    json={"model": self.model, "input": batch},
                    headers=headers,
                )
            except httpx.ConnectError as exc:
                raise ImproperlyConfigured(
                    f"The embeddings endpoint is unreachable at {self.url}. Start "
                    "the `embeddings` Compose profile or `just embedder-local`."
                ) from exc
            if response.status_code != 200:
                raise ExternalServiceError(
                    f"Embeddings endpoint returned {response.status_code}: "
                    f"{response.text[:200]}",
                    code="embeddings_error",
                )
            data = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors.extend(item["embedding"] for item in data)
        for vector in vectors:
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise ImproperlyConfigured(
                    f"{self.model} returned {len(vector)}-dimension vectors; the "
                    f"fixture column holds {EMBEDDING_DIMENSIONS}. Use "
                    "Qwen3-Embedding-0.6B or change EMBEDDING_DIMENSIONS with a "
                    "migration."
                )
        return vectors

    def query_text(self, text: str) -> str:
        """Prefix *text* with the retrieval instruction Qwen3-Embedding expects."""
        return (
            f"Instruct: {self.instruction}\nQuery:{text}" if self.instruction else text
        )

    def embed_fixtures(self, kind: str | None = None, force: bool = False) -> int:
        """Embed fixtures that have no vector yet (or all, with *force*).

        Returns:
            The number of fixtures embedded.
        """
        queryset = DecisionFixture.objects.all()
        if kind:
            queryset = queryset.filter(kind=kind)
        if not force:
            queryset = queryset.filter(embedding=None)
        fixtures = list(queryset.order_by("kind", "name"))
        if not fixtures:
            return 0
        vectors = self.embed([fixture_text(f) for f in fixtures])
        for fixture, vector in zip(fixtures, vectors, strict=True):
            fixture.embedding = vector
        DecisionFixture.objects.bulk_update(fixtures, ["embedding"])
        logger.info("Embedded %s decision fixtures with %s", len(fixtures), self.model)
        return len(fixtures)

    def similar(
        self, text: str, kind: str | None = None, limit: int = 5
    ) -> list[tuple[DecisionFixture, float]]:
        """Return up to *limit* embedded fixtures nearest to *text*.

        Each item pairs a fixture with its cosine distance (0 is identical).
        Needs PostgreSQL with pgvector.
        """
        (vector,) = self.embed([self.query_text(text)])
        queryset = DecisionFixture.objects.exclude(embedding=None)
        if kind:
            queryset = queryset.filter(kind=kind)
        ranked = queryset.annotate(
            distance=CosineDistance("embedding", vector)
        ).order_by("distance")[:limit]
        # `distance` is the annotation above; the model class does not declare it.
        return [(fixture, float(cast("Any", fixture).distance)) for fixture in ranked]
