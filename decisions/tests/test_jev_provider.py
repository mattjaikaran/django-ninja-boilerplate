"""Tests for the Jev (TypeSafe) provider.

The ``typesafe-sdk`` package and ``TYPESAFE_API_KEY`` are absent from the
test environment, so these tests cover the fail-loud behaviour and the
response mapping.
"""

from types import SimpleNamespace

import pytest
from django.core.exceptions import ImproperlyConfigured

from decisions.providers import JevProvider


class _StubClient:
    """Client that returns a fixed mapping."""

    def __init__(self, response):
        self.response = response

    def system_one(self, state, questions):
        return self.response


@pytest.mark.unit
class TestJevAvailability:
    """Availability requires both a key and a client or the package."""

    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.setattr("decisions.providers.jev._sdk_installed", lambda: True)
        assert JevProvider(api_key="").is_available() is False

    def test_available_with_key_and_injected_client(self):
        assert JevProvider(client=_StubClient({}), api_key="key").is_available() is True

    def test_unavailable_without_package(self, monkeypatch):
        monkeypatch.setattr("decisions.providers.jev._sdk_installed", lambda: False)
        assert JevProvider(api_key="key").is_available() is False


@pytest.mark.unit
class TestJevFailLoud:
    """A missing key raises a clear configuration error."""

    def test_predict_without_key_raises(self):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            JevProvider(api_key="").predict({}, {})
        assert "TYPESAFE_API_KEY" in str(exc_info.value)


@pytest.mark.unit
class TestJevMapping:
    """Client responses are normalised to a DecisionResult."""

    def test_maps_client_response(self):
        client = _StubClient(
            {
                "answers": {"risk": {"choice": "escalate", "confidence": 0.64}},
                "routing": {"model": "jev", "reason": "hosted"},
                "provider": "jev",
            }
        )
        result = JevProvider(client=client, api_key="key").predict({"a": 1}, {})
        assert result.answers == {"risk": "escalate"}
        assert result.answer_confidence == {"risk": 0.64}
        assert result.confidence == 0.64
        assert result.provider == "jev"
        assert result.routing == {"model": "jev", "reason": "hosted"}
        assert result.escalation_recommended is False

    def test_maps_typed_sdk_answers_and_noul_uncertainty(self):
        client = _StubClient(
            SimpleNamespace(
                answers={
                    "department": SimpleNamespace(choice="billing", confidence=0.93),
                    "urgency": SimpleNamespace(noul=0.2),
                    "severity": SimpleNamespace(score=1.5, confidence=0.81),
                }
            )
        )
        result = JevProvider(client=client, api_key="key").predict(
            {"ticket": "late payment"}, {}
        )
        assert result.answers == {
            "department": "billing",
            "urgency": 0.2,
            "severity": 1.5,
        }
        assert result.answer_confidence == {
            "department": 0.93,
            "urgency": 0.8,
            "severity": 0.81,
        }
        assert result.confidence == 0.8
