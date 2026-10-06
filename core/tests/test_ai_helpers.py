"""Hybrid-search fusion order, owner scoping, and the LLM response cache key."""

from typing import Any

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import connection

from core.ai.services import (
    hybrid_search,
    prompt_cache_key,
    reachable,
    reciprocal_rank_fusion,
)

needs_ai_db = pytest.mark.skipif(
    not apps.is_installed("core.ai") or connection.vendor != "postgresql",
    reason="Needs AI_ENABLED=true and Postgres with pgvector (CI=1).",
)


def _user(username: str) -> Any:
    return get_user_model().objects.create_user(  # type: ignore[attr-defined]
        username=username, email=f"{username}@example.com", password="x-Pass-123!"
    )


@needs_ai_db
@pytest.mark.django_db
def test_hybrid_search_returns_only_the_callers_documents():
    from core.ai.models import EMBEDDING_DIMENSIONS, Document

    alice, bob = _user("alice"), _user("bob")
    vector = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
    doc = Document.objects.create(
        owner=alice, title="Payroll secrets", body="salary", embedding=vector
    )
    search = {"text": "payroll", "embedding": vector}

    def found(user: Any) -> list[Any]:
        hits = hybrid_search(Document.objects.all(), user=user, **search)
        return [hit.obj.pk for hit in hits]

    assert found(alice) == [doc.pk]
    assert found(bob) == []
    assert found(AnonymousUser()) == []
    assert found(None) == []


@needs_ai_db
@pytest.mark.django_db
def test_reachable_does_not_walk_into_or_from_other_users_documents():
    from core.ai.models import Document, DocumentLink

    alice, bob = _user("alice"), _user("bob")
    a1 = Document.objects.create(owner=alice, title="a1", body="x")
    a2 = Document.objects.create(owner=alice, title="a2", body="x")
    b1 = Document.objects.create(owner=bob, title="b1", body="x")
    DocumentLink.objects.create(source=a1, target=a2)
    DocumentLink.objects.create(source=a1, target=b1)
    DocumentLink.objects.create(source=b1, target=a2)

    assert reachable(DocumentLink, a1.pk, user=alice) == [(a2.pk, 1)]
    assert reachable(DocumentLink, a1.pk, user=bob) == []
    assert reachable(DocumentLink, b1.pk, user=alice) == []
    assert reachable(DocumentLink, a1.pk, user=None) == []


def test_rrf_ranks_a_key_found_by_both_rankings_first():
    lexical = ["both", "text-only"]
    semantic = ["vector-only", "both"]
    fused = reciprocal_rank_fusion([lexical, semantic], k=60)
    # both: 1/61 + 1/62; vector-only: 1/61 (rank 1); text-only: 1/62 (rank 2).
    assert [key for key, _ in fused] == ["both", "vector-only", "text-only"]
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 62)


def test_rrf_breaks_ties_by_first_appearance():
    fused = reciprocal_rank_fusion([["a"], ["b"]], k=60)
    assert fused == [("a", pytest.approx(1 / 61)), ("b", pytest.approx(1 / 61))]


def test_cache_key_ignores_dict_order_but_not_content():
    messages = [{"role": "user", "content": "hi"}]
    reordered = [{"content": "hi", "role": "user"}]
    key = prompt_cache_key("m", messages, temperature=0, max_tokens=5)
    assert key == prompt_cache_key("m", reordered, max_tokens=5, temperature=0)
    assert key != prompt_cache_key("other", messages, temperature=0, max_tokens=5)
    assert key != prompt_cache_key("m", messages, temperature=1, max_tokens=5)
    assert key != prompt_cache_key(
        "m", [{"role": "user", "content": "hi!"}], temperature=0, max_tokens=5
    )
