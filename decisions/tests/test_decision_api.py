"""Integration tests for the decisions API endpoint."""

import json

import pytest

from core.tests.factories import UserFactory
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

    def test_evaluate_with_fake_provider(self, authenticated_client):
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
                "provider": "fake",
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

    def test_empty_questions_is_valid(self, authenticated_client):
        response = _post(
            authenticated_client, {"state": {}, "questions": {}, "provider": "fake"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["answers"] == {}
        assert body["confidence"] == 0.0
        assert body["escalationRecommended"] is False

    def test_invalid_provider_rejected_by_schema(self, authenticated_client):
        response = _post(
            authenticated_client, {"state": {}, "questions": {}, "provider": "bogus"}
        )
        assert response.status_code == 422

    def test_invalid_question_type_rejected_by_schema(self, authenticated_client):
        response = _post(
            authenticated_client,
            {
                "state": {},
                "questions": {"q": {"type": "yesno", "instructions": "?"}},
                "provider": "fake",
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
        assert "uv sync --extra decisions-laya" in response.json()["message"]
