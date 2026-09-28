"""Tests for the Laya provider.

Tests simulate a missing dependency and check package loading without
downloading a model or making a network request.
"""

import sys
import types

import pytest
from django.core.exceptions import ImproperlyConfigured

from decisions.providers import LayaProvider
from decisions.providers.laya import INSTALL_HINT

#: A response in Laya's documented shape.
LAYA_RESPONSE = {
    "answers": {
        "department": {"choice": "billing", "confidence": 0.94},
        "urgency": {"score": 0.8, "confidence": 0.71},
        "churn_risk": {"noul": True, "confidence": 0.88},
    },
    "routing": {
        "model": "english",
        "repo": "convaiinnovations/laya",
        "reason": "Latin script",
    },
}


class _StubEngine:
    """Engine that returns a fixed mapping."""

    def __init__(self, response=None, **kwargs):
        self.response = response if response is not None else {}
        self.kwargs = kwargs

    def predict(self, state, questions):
        return self.response


@pytest.mark.unit
class TestLayaAvailability:
    """Availability reflects the installed package or an injected router."""

    def test_unavailable_when_package_missing(self, monkeypatch):
        monkeypatch.setattr("decisions.providers.laya._laya_installed", lambda: False)
        assert LayaProvider().is_available() is False

    def test_available_with_injected_router(self):
        assert LayaProvider(router=_StubEngine()).is_available() is True

    def test_available_when_package_present(self, monkeypatch):
        monkeypatch.setattr("decisions.providers.laya._laya_installed", lambda: True)
        assert LayaProvider().is_available() is True


@pytest.mark.unit
class TestLayaFailLoud:
    """A missing package raises a clear configuration error."""

    def test_predict_raises_with_install_hint(self, monkeypatch):
        monkeypatch.setattr("decisions.providers.laya._laya_installed", lambda: False)
        with pytest.raises(ImproperlyConfigured) as exc_info:
            LayaProvider().predict({}, {})
        assert INSTALL_HINT in str(exc_info.value)
        assert "uv sync --locked" in str(exc_info.value)

    def test_error_is_not_swallowed_into_a_fallback(self, monkeypatch):
        monkeypatch.setattr("decisions.providers.laya._laya_installed", lambda: False)
        with pytest.raises(ImproperlyConfigured):
            LayaProvider().predict({"state": 1}, {"q": {"type": "choice"}})


@pytest.mark.unit
class TestLayaRouterLoading:
    """The router is imported from the package and built once."""

    def test_builds_router_with_preload(self, monkeypatch):
        created = {}

        class Engine:
            def __init__(self, preload=False):
                created["preload"] = preload

        module = types.ModuleType("laya")
        module.__dict__["Router"] = Engine
        monkeypatch.setitem(sys.modules, "laya", module)
        monkeypatch.setattr("decisions.providers.laya._laya_installed", lambda: True)

        provider = LayaProvider(preload=True)
        router = provider._get_router()
        assert isinstance(router, Engine)
        assert created["preload"] is True
        # The router is cached, not rebuilt.
        assert provider._get_router() is router


@pytest.mark.unit
class TestLayaMapping:
    """Laya's response shape is normalised faithfully."""

    def test_maps_typed_answers(self):
        result = LayaProvider(router=_StubEngine(LAYA_RESPONSE)).predict({"a": 1}, {})
        assert result.answers == {
            "department": "billing",
            "urgency": 0.8,
            "churn_risk": True,
        }
        assert result.answer_confidence == {
            "department": 0.94,
            "urgency": 0.71,
            "churn_risk": 0.88,
        }

    def test_aggregate_confidence_is_the_weakest_answer(self):
        result = LayaProvider(router=_StubEngine(LAYA_RESPONSE)).predict({}, {})
        assert result.confidence == 0.71

    def test_routing_metadata_is_preserved(self):
        result = LayaProvider(router=_StubEngine(LAYA_RESPONSE)).predict({}, {})
        assert result.routing == LAYA_RESPONSE["routing"]
        assert result.provider == "laya"

    def test_sparse_response(self):
        result = LayaProvider(router=_StubEngine({})).predict({}, {})
        assert result.answers == {}
        assert result.confidence == 0.0
        assert result.provider == "laya"
