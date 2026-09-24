"""Tests for DecisionService provider selection, policy, and fixtures."""

import json

import pytest
from django.core.exceptions import ImproperlyConfigured

from api.exceptions import ValidationError
from decisions.models import DecisionFixture
from decisions.providers import (
    DecisionProvider,
    DecisionResult,
    FakeProvider,
)
from decisions.services import DecisionService
from decisions.tests.factories import DecisionFixtureFactory

NOUL_QUESTION = {"churn": {"type": "noul", "instructions": "Will they cancel?"}}


class _EscalatingProvider(DecisionProvider):
    """Provider that flags escalation itself."""

    name = "fake"

    def is_available(self) -> bool:
        return True

    def predict(self, state, questions) -> DecisionResult:
        return DecisionResult(
            answers={"churn": True},
            answer_confidence={"churn": 0.99},
            confidence=0.99,
            provider=self.name,
            escalation_recommended=True,
        )


@pytest.fixture(autouse=True)
def clear_provider_cache():
    """Reset the class-level provider cache around each test."""
    DecisionService._providers.clear()
    yield
    DecisionService._providers.clear()


@pytest.mark.unit
class TestProviderSelection:
    """The service resolves a provider from settings or an argument."""

    def test_default_provider_comes_from_settings(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        assert DecisionService().provider_name == "fake"

    def test_explicit_provider_argument_wins(self, settings):
        settings.SYSTEMONE_PROVIDER = "laya"
        assert DecisionService(provider="fake").provider_name == "fake"

    def test_unknown_provider_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            DecisionService().get_provider("nope")
        assert "nope" in exc_info.value.message

    def test_provider_instances_are_cached(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        service = DecisionService()
        assert service.get_provider() is service.get_provider()
        assert isinstance(service.get_provider(), FakeProvider)


@pytest.mark.unit
class TestDecide:
    """``decide`` delegates to the selected provider."""

    def test_decide_uses_selected_provider(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        result = DecisionService().decide({}, NOUL_QUESTION)
        assert result.answers == {"churn": False}
        assert result.answer_confidence == {"churn": 0.99}
        assert result.provider == "fake"

    def test_decide_provider_override(self, settings):
        settings.SYSTEMONE_PROVIDER = "laya"
        result = DecisionService().decide({}, {}, provider="fake")
        assert result.provider == "fake"

    def test_decide_default_laya_fails_loud(self, settings, monkeypatch):
        monkeypatch.setattr("decisions.providers.laya._laya_installed", lambda: False)
        settings.SYSTEMONE_PROVIDER = "laya"
        with pytest.raises(ImproperlyConfigured):
            DecisionService().decide({}, {})


@pytest.mark.unit
class TestEscalationPolicy:
    """Weak results are flagged; empty or strong results are not."""

    def test_strong_result_is_not_escalated(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        assert (
            DecisionService().decide({}, NOUL_QUESTION).escalation_recommended is False
        )

    def test_weak_result_is_escalated(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        DecisionService._providers["fake"] = FakeProvider(confidence=0.2)
        result = DecisionService().decide({}, NOUL_QUESTION)
        assert result.confidence == 0.2
        assert result.escalation_recommended is True

    def test_threshold_comes_from_settings(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        settings.DECISION_ESCALATION_THRESHOLD = 0.1
        DecisionService._providers["fake"] = FakeProvider(confidence=0.2)
        result = DecisionService().decide({}, NOUL_QUESTION)
        assert result.escalation_recommended is False

    def test_empty_request_is_not_escalated(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        DecisionService._providers["fake"] = FakeProvider(confidence=0.0)
        result = DecisionService().decide({}, {})
        assert result.confidence == 0.0
        assert result.escalation_recommended is False

    def test_provider_flag_is_kept(self, settings):
        settings.SYSTEMONE_PROVIDER = "fake"
        DecisionService._providers["fake"] = _EscalatingProvider()
        result = DecisionService().decide({}, NOUL_QUESTION)
        assert result.confidence == 0.99
        assert result.escalation_recommended is True


@pytest.mark.django_db
class TestFixtures:
    """Fixture listing and seeding."""

    def test_list_fixtures_filters_by_kind(self):
        DecisionFixtureFactory(kind="support_ticket", name="a")
        DecisionFixtureFactory(kind="api_payload", name="b")
        assert DecisionService().list_fixtures(kind="api_payload").count() == 1
        assert DecisionService().list_fixtures().count() == 2

    def test_seed_fixtures_is_idempotent(self, tmp_path):
        (tmp_path / "one.json").write_text(
            json.dumps(
                {
                    "kind": "support_ticket",
                    "fixtures": [{"name": "x", "payload": {"a": 1}}],
                }
            ),
            encoding="utf-8",
        )
        service = DecisionService()
        assert service.seed_fixtures(tmp_path) == {"created": 1, "updated": 0}
        assert service.seed_fixtures(tmp_path) == {"created": 0, "updated": 1}
        assert (
            DecisionFixture.objects.filter(kind="support_ticket", name="x").count() == 1
        )

    def test_seed_fixtures_requires_kind(self, tmp_path):
        (tmp_path / "bad.json").write_text(
            json.dumps({"fixtures": []}), encoding="utf-8"
        )
        with pytest.raises(ValueError):
            DecisionService().seed_fixtures(tmp_path)
