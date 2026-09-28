"""Verify CLM wire decisions and explicit provider failure behavior."""

import json

import httpx
import pytest
from django.core.exceptions import ImproperlyConfigured

from decisions.providers.clm import ClmProvider
from decisions.services import DecisionService


@pytest.mark.unit
class TestClmProvider:
    def test_clm_wire_response_preserves_strong_no_and_selected_options(self):
        observed = []

        def respond(request):
            observed.append(request)
            return httpx.Response(
                200,
                json={
                    "model": "clm-latest",
                    "answers": {
                        "risk": {"type": "noul", "noul": 0.03},
                        "worker": {
                            "type": "choice",
                            "choice": "review",
                            "confidence": 0.95,
                            "probabilities": {"review": 0.95, "write": 0.05},
                        },
                        "urgency": {
                            "type": "score",
                            "score": 1.25,
                            "confidence": 0.81,
                            "probabilities": {"0": 0.1, "1": 0.55, "2": 0.35},
                        },
                    },
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(respond))
        provider = ClmProvider(
            client=client, base_url="http://clm-api:8700/", api_key="private"
        )
        state = {"ticket": "T-1"}
        questions = {
            "risk": {"type": "noul", "instructions": "Is there risk?"},
            "worker": {
                "type": "choice",
                "instructions": "Choose the next worker",
                "criteria": {"review": "Review", "write": "Write"},
            },
            "urgency": {
                "type": "score",
                "instructions": "How urgent?",
                "criteria": ["Low", "Medium", "High"],
            },
        }
        result = provider.predict(state, questions)
        assert result.answers == {"risk": 0.03, "worker": "review", "urgency": 1.25}
        assert result.answer_confidence == {
            "risk": 0.97,
            "worker": 0.95,
            "urgency": 0.81,
        }
        assert result.confidence == 0.81
        assert result.provider == "clm"
        assert result.fallback_used is False
        assert observed[0].url == "http://clm-api:8700/v1/systemone"
        assert observed[0].headers["Authorization"] == "Bearer private"
        assert json.loads(observed[0].read()) == {
            "state": state,
            "questions": questions,
        }

    def test_clm_error_never_falls_back_to_another_provider(self):
        client = httpx.Client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(503))
        )
        provider = ClmProvider(client=client, base_url="http://clm-api:8700")
        with pytest.raises(httpx.HTTPStatusError) as error:
            provider.predict({}, {"q": {"type": "noul", "instructions": "?"}})
        assert error.value.response.status_code == 503

    def test_missing_endpoint_fails_with_setup_instructions(self):
        provider = ClmProvider(base_url="")
        assert provider.is_available() is False
        with pytest.raises(ImproperlyConfigured, match="CLM_BASE_URL"):
            provider.predict({}, {})

    def test_missing_clm_answer_is_rejected(self):
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json={"answers": {}})
            )
        )
        provider = ClmProvider(client=client, base_url="http://clm-api:8700")
        with pytest.raises(ValueError, match="omitted"):
            provider.predict({}, {"risk": {"type": "noul", "instructions": "Risk?"}})

    def test_default_provider_switches_using_configuration(self, settings):
        settings.SYSTEMONE_PROVIDER = "clm"
        assert DecisionService().provider_name == "clm"
        settings.SYSTEMONE_PROVIDER = "laya"
        assert DecisionService().provider_name == "laya"
        settings.SYSTEMONE_PROVIDER = "jev"
        assert DecisionService().provider_name == "jev"
