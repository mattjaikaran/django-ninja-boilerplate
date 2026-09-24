"""Tests for the DecisionFixture model."""

from typing import cast

import pytest
from django.db import IntegrityError, transaction

from decisions.models import EMBEDDING_DIMENSIONS, DecisionFixture
from decisions.tests.factories import DecisionFixtureFactory


@pytest.mark.django_db
class TestDecisionFixtureModel:
    """Model behaviour and the pgvector column."""

    def test_create(self):
        fixture = DecisionFixtureFactory(kind="support_ticket", name="refund")
        assert fixture.kind == "support_ticket"
        assert fixture.name == "refund"
        assert str(fixture) == "support_ticket:refund"

    def test_kind_and_name_are_unique_together(self):
        DecisionFixtureFactory(kind="api_payload", name="dup")
        with pytest.raises(IntegrityError), transaction.atomic():
            DecisionFixtureFactory(kind="api_payload", name="dup")

    def test_same_name_in_a_different_kind_is_allowed(self):
        DecisionFixtureFactory(kind="api_payload", name="dup")
        DecisionFixtureFactory(kind="support_ticket", name="dup")
        assert DecisionFixture.objects.filter(name="dup").count() == 2

    def test_default_ordering(self):
        DecisionFixtureFactory(kind="support_ticket", name="b")
        DecisionFixtureFactory(kind="api_payload", name="a")
        assert [f.kind for f in DecisionFixture.objects.all()] == [
            "api_payload",
            "support_ticket",
        ]

    def test_embedding_defaults_to_null(self):
        assert DecisionFixtureFactory().embedding is None

    def test_embedding_round_trips(self):
        vector = [0.5] * EMBEDDING_DIMENSIONS
        fixture = cast("DecisionFixture", DecisionFixtureFactory(embedding=vector))
        fixture.refresh_from_db()
        assert fixture.embedding is not None
        assert list(fixture.embedding) == vector
