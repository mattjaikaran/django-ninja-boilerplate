"""Tests for fixture embeddings and similarity search."""

import json

import httpx
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from api.exceptions import ExternalServiceError
from decisions.models import DecisionFixture
from decisions.models.decision_fixture import EMBEDDING_DIMENSIONS
from decisions.services import DecisionService, FixtureEmbeddingService
from decisions.services.embedding_service import fixture_text
from decisions.tests.factories import DecisionFixtureFactory


def _unit(index: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


def _service(vector_for, seen=None, **kwargs):
    """Service whose endpoint maps each input text to a vector."""

    def respond(request):
        body = json.loads(request.read())
        if seen is not None:
            seen.append(body)
        data = [
            {"index": i, "embedding": vector_for(text)}
            for i, text in enumerate(body["input"])
        ]
        return httpx.Response(200, json={"data": list(reversed(data))})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    return FixtureEmbeddingService(
        client=client, url="http://embedder:8080/v1/embeddings", **kwargs
    )


@pytest.mark.django_db
class TestEmbedFixtures:
    def test_fills_only_missing_vectors_in_input_order(self):
        kept = DecisionFixtureFactory(name="kept", embedding=_unit(5))
        DecisionFixtureFactory(name="a", description="alpha")
        DecisionFixtureFactory(name="b", description="beta")
        seen: list = []
        service = _service(lambda t: _unit(1 if "alpha" in t else 2), seen)
        assert service.embed_fixtures() == 2
        assert seen[0]["model"] == "qwen3-embedding-0.6b"
        vectors = {f.name: list(f.embedding) for f in DecisionFixture.objects.all()}
        assert vectors["a"] == _unit(1)
        assert vectors["b"] == _unit(2)
        assert vectors[kept.name] == _unit(5)

    def test_force_recomputes_every_vector(self):
        DecisionFixtureFactory(embedding=_unit(5))
        assert _service(lambda _t: _unit(3)).embed_fixtures(force=True) == 1

    def test_wrong_width_fails_loud(self):
        DecisionFixtureFactory()
        with pytest.raises(ImproperlyConfigured, match="768-dimension"):
            _service(lambda _t: [0.1] * 768).embed_fixtures()

    def test_endpoint_error_is_raised(self):
        client = httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(503, text="busy"))
        )
        service = FixtureEmbeddingService(client=client, url="http://embedder")
        with pytest.raises(ExternalServiceError, match="503"):
            service.embed(["x"])

    def test_unreachable_endpoint_names_the_url(self):
        def refuse(request):
            raise httpx.ConnectError("refused", request=request)

        client = httpx.Client(transport=httpx.MockTransport(refuse))
        service = FixtureEmbeddingService(client=client, url="http://embedder:8080")
        with pytest.raises(
            ImproperlyConfigured, match="unreachable at http://embedder"
        ):
            service.embed(["x"])

    def test_empty_url_fails_with_setup_hint(self):
        with pytest.raises(ImproperlyConfigured, match="DECISION_EMBEDDING_URL"):
            FixtureEmbeddingService(url="").embed(["x"])


@pytest.mark.unit
def test_query_carries_the_instruction_and_documents_do_not():
    service = FixtureEmbeddingService(url="x", instruction="Find similar cases")
    assert service.query_text("broken box") == (
        "Instruct: Find similar cases\nQuery:broken box"
    )
    fixture = DecisionFixture(description="Damaged parcel", payload={"order": 7})
    assert fixture_text(fixture) == "Damaged parcel\n\norder: 7"


@pytest.mark.django_db
class TestSeedKeepsFreshVectors:
    def _write(self, tmp_path, payload):
        (tmp_path / "t.json").write_text(
            json.dumps(
                {
                    "kind": "support_ticket",
                    "fixtures": [{"name": "n", "payload": payload}],
                }
            )
        )

    def test_unchanged_fixture_keeps_its_vector_and_changed_one_is_cleared(
        self, tmp_path
    ):
        self._write(tmp_path, {"a": 1})
        DecisionService().seed_fixtures(tmp_path)
        DecisionFixture.objects.update(embedding=_unit(1))

        DecisionService().seed_fixtures(tmp_path)
        assert DecisionFixture.objects.get().embedding is not None

        self._write(tmp_path, {"a": 2})
        DecisionService().seed_fixtures(tmp_path)
        assert DecisionFixture.objects.get().embedding is None


@pytest.mark.django_db
@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="cosine distance needs pgvector"
)
def test_similar_orders_by_cosine_distance():
    DecisionFixtureFactory(name="far", embedding=_unit(9))
    DecisionFixtureFactory(name="near", embedding=_unit(1))
    DecisionFixtureFactory(name="unembedded")
    matches = _service(lambda _t: _unit(1)).similar("query", limit=5)
    assert [(f.name, round(d, 3)) for f, d in matches] == [("near", 0.0), ("far", 1.0)]
