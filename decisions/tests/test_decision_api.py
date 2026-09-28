"""Integration tests for the decisions API endpoint."""

import json

import httpx
import pytest

from core.tests.factories import UserFactory
from decisions.providers.clm import ClmProvider
from decisions.services import DecisionService


@pytest.fixture
def authenticated_client(api_client):
    from ninja_jwt.tokens import RefreshToken

    user = UserFactory()
    refresh = RefreshToken.for_user(user)
    api_client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {refresh.access_token}"
    return api_client


EVALUATE_URL = "/api/decisions/evaluate"


@pytest.fixture(autouse=True)
def clear_provider_cache():
    """Reset the class-level provider cache around each test."""
    DecisionService._providers.clear()
    yield
    DecisionService._providers.clear()


def _post(client, payload):
    """POST *payload* to the evaluate endpoint as JSON."""
    return client.post(
        EVALUATE_URL, data=json.dumps(payload), content_type="application/json"
    )


@pytest.mark.django_db
class TestEvaluateEndpoint:
    """The endpoint returns a decision or a clear provider error."""

    def test_evaluate_with_configured_fake_provider(
        self, authenticated_client, settings
    ):
        settings.SYSTEMONE_PROVIDER = "fake"
        response = _post(
            authenticated_client,
            {
                "state": {"ticket": "T-1"},
                "questions": {
                    "risk": {
                        "type": "choice",
                        "instructions": "Approve?",
                        "criteria": {"approve": "ok", "deny": "no"},
                    }
                },
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "fake"
        assert body["answers"] == {"risk": "approve"}
        assert body["answerConfidence"] == {"risk": 0.99}
        assert body["confidence"] == 0.99
        assert body["routing"] is None
        assert body["fallbackUsed"] is False
        assert body["escalationRecommended"] is False

    def test_empty_questions_is_valid(self, authenticated_client, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        response = _post(authenticated_client, {"state": {}, "questions": {}})
        assert response.status_code == 200
        body = response.json()
        assert body["answers"] == {}
        assert body["confidence"] == 0.0
        assert body["escalationRecommended"] is False

    def test_invalid_question_type_rejected_by_schema(
        self, authenticated_client, settings
    ):
        settings.SYSTEMONE_PROVIDER = "fake"
        response = _post(
            authenticated_client,
            {
                "state": {},
                "questions": {"q": {"type": "yesno", "instructions": "?"}},
            },
        )
        assert response.status_code == 422

    def test_default_provider_fails_loud_with_instructions(
        self, authenticated_client, monkeypatch, settings
    ):
        monkeypatch.setattr("decisions.providers.laya._laya_installed", lambda: False)
        settings.SYSTEMONE_PROVIDER = "laya"
        response = _post(
            authenticated_client,
            {
                "state": {},
                "questions": {"risk": {"type": "choice", "instructions": "Approve?"}},
            },
        )
        assert response.status_code == 500
        assert "uv sync --locked" in response.json()["message"]

    def test_configured_clm_provider_answers(self, authenticated_client, settings):
        settings.SYSTEMONE_PROVIDER = "clm"
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={
                        "model": "clm-latest",
                        "answers": {"risk": {"type": "noul", "noul": 0.02}},
                    },
                )
            )
        )
        DecisionService._providers["clm"] = ClmProvider(
            client=client, base_url="http://clm-api:8700"
        )
        response = _post(
            authenticated_client,
            {
                "state": {"ticket": "T-1"},
                "questions": {
                    "risk": {"type": "noul", "instructions": "Is there risk?"}
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["provider"] == "clm"
        assert response.json()["answers"] == {"risk": 0.02}
        assert response.json()["answerConfidence"] == {"risk": 0.98}
        assert response.json()["escalationRecommended"] is False

    @pytest.mark.parametrize("override", ["fake", "jev", "laya", "clm"])
    def test_client_cannot_override_configured_provider(
        self, authenticated_client, settings, override
    ):
        settings.SYSTEMONE_PROVIDER = "clm"
        calls = []

        def respond(request):
            calls.append(request)
            return httpx.Response(200, json={"answers": {}})

        DecisionService._providers["clm"] = ClmProvider(
            client=httpx.Client(transport=httpx.MockTransport(respond)),
            base_url="http://clm-api:8700",
        )
        response = _post(
            authenticated_client,
            {"state": {}, "questions": {}, "provider": override},
        )
        assert response.status_code == 422
        assert calls == []
        assert set(DecisionService._providers) == {"clm"}


SIMILAR_URL = "/api/decisions/similar"


@pytest.mark.django_db
class TestSimilarEndpoint:
    """Similarity search validates input and fails loud without an embedder."""

    def test_missing_embedder_returns_setup_hint(self, authenticated_client, settings):
        settings.DECISION_EMBEDDING_URL = ""
        response = authenticated_client.post(
            SIMILAR_URL,
            data=json.dumps({"text": "broken parcel"}),
            content_type="application/json",
        )
        assert response.status_code == 500
        assert response.json()["error"] == "embeddings_unavailable"
        assert "DECISION_EMBEDDING_URL" in response.json()["message"]

    @pytest.mark.parametrize(
        "payload",
        [{"text": ""}, {"text": "x", "limit": 50}, {"text": "x", "kind": "other"}],
    )
    def test_invalid_requests_are_rejected(self, authenticated_client, payload):
        response = authenticated_client.post(
            SIMILAR_URL, data=json.dumps(payload), content_type="application/json"
        )
        assert response.status_code == 422
