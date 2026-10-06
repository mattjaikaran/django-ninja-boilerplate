"""Hybrid search: Postgres full-text search plus pgvector, fused with RRF."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F

if TYPE_CHECKING:
    from collections.abc import Hashable, Sequence

    from django.contrib.auth.base_user import AbstractBaseUser
    from django.contrib.auth.models import AnonymousUser
    from django.db.models import Model, QuerySet

# k from Cormack, Clarke and Buettcher, "Reciprocal Rank Fusion outperforms
# Condorcet and individual Rank Learning Methods" (SIGIR 2009). A larger k
# shrinks the lead of the top ranks.
RRF_K = 60
# An HNSW index scan returns at most `hnsw.ef_search` rows (pgvector default
# 40). More candidates than that silently returns fewer vector hits.
DEFAULT_CANDIDATES = 40


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Hashable]], k: int = RRF_K
) -> list[tuple[Hashable, float]]:
    """Fuse ranked lists of keys into one list of (key, score), best first.

    score(key) = sum over rankings of 1 / (k + rank), rank starting at 1. A
    key missing from a ranking adds nothing for it. Equal scores keep the
    order in which the keys first appear (earlier rankings first).
    """
    scores: dict[Hashable, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


@dataclass(frozen=True)
class HybridHit:
    obj: Any
    score: float


def hybrid_search(
    queryset: QuerySet[Model],
    *,
    user: AbstractBaseUser | AnonymousUser | None,
    text: str,
    embedding: Sequence[float],
    owner_field: str = "owner",
    search_field: str = "search_vector",
    embedding_field: str = "embedding",
    config: str = "english",
    limit: int = 10,
    candidates: int = DEFAULT_CANDIDATES,
) -> list[HybridHit]:
    """Rank the caller's rows by full-text match and by vector similarity.

    The search only sees rows where ``owner_field`` is ``user``. No user, or
    an anonymous user, returns no hits. ``search_field`` is a
    ``SearchVectorField`` (GIN-indexed) and ``embedding_field`` a pgvector
    ``VectorField`` with a ``vector_cosine_ops`` HNSW index. Each side keeps
    its top ``candidates``.
    """
    from pgvector.django import CosineDistance

    if user is None or not user.is_authenticated:
        return []
    queryset = queryset.filter(**{owner_field: user})
    query = SearchQuery(text, config=config, search_type="websearch")
    lexical = list(
        queryset.filter(**{search_field: query})
        .annotate(fts_rank=SearchRank(F(search_field), query))
        .order_by("-fts_rank")
        .values_list("pk", flat=True)[:candidates]
    )
    semantic = list(
        queryset.filter(**{f"{embedding_field}__isnull": False})
        .order_by(CosineDistance(embedding_field, embedding))
        .values_list("pk", flat=True)[:candidates]
    )
    fused = reciprocal_rank_fusion([lexical, semantic])[:limit]
    objects = queryset.in_bulk([pk for pk, _ in fused])
    return [HybridHit(objects[pk], score) for pk, score in fused if pk in objects]
