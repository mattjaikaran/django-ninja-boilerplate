"""Owner scoping for hybrid search and document-link graph walks."""

from typing import Any

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import connection

from core.ai.services import hybrid_search, reachable

needs_ai_db = pytest.mark.skipif(
    not apps.is_installed("core.ai") or connection.vendor != "postgresql",
    reason="Needs AI_ENABLED=true and Postgres with pgvector (TEST_DB=postgres).",
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
