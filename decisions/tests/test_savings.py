"""Tests for the baseline LLM client and token-savings measurement."""

import json

import httpx
import pytest
from django.core.exceptions import ImproperlyConfigured

from decisions.providers.base import DecisionProvider, DecisionResult
from decisions.services import DecisionService
from decisions.services.agent_service import pack_questions
from decisions.services.llm_baseline import BaselineLLM, parse_answers
from decisions.services.savings_service import (
    DecisionSavingsService,
    FlowItem,
    roadmap_tasks,
)

ROUTE = pack_questions("route_task")


def _llm(replies, prompt_tokens=100, completion_tokens=10, status=200):
    """Return a BaselineLLM whose endpoint replies with *replies* in order."""
    queue = list(replies)
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        body = {
            "choices": [{"message": {"content": queue.pop(0)}}],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
        }
        return httpx.Response(status, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = BaselineLLM(client=client, url="http://llm/v1/chat/completions", model="m")
    return llm, sent


class _Confidences(DecisionProvider):
    """Answer route_task with a per-call confidence (a float or a mapping)."""

    name = "scripted"

    def __init__(self, confidences):
        self.confidences = list(confidences)

    def is_available(self) -> bool:
        return True

    def predict(self, state, questions) -> DecisionResult:
        conf = self.confidences.pop(0)
        per = {k: conf[k] if isinstance(conf, dict) else conf for k in questions}
        return DecisionResult(
            answers={"tier": "local", "needs_human": False},
            answer_confidence=per,
            confidence=min(per.values()),
            provider=self.name,
        )


@pytest.fixture(autouse=True)
def clean(settings):
    settings.DECISION_THRESHOLDS_FILE = ""
    settings.DECISION_ESCALATION_THRESHOLD = 0.5
    settings.DECISION_LLM_INPUT_PRICE_PER_MTOK = None
    settings.DECISION_LLM_OUTPUT_PRICE_PER_MTOK = None
    DecisionService._providers.clear()
    yield
    DecisionService._providers.clear()


@pytest.mark.unit
class TestParseAnswers:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            (
                '{"tier": "mid", "needs_human": false}',
                {"tier": "mid", "needs_human": False},
            ),
            (
                '```json\n{"tier": "local", "needs_human": "true"}\n```',
                {"tier": "local", "needs_human": True},
            ),
            ('{"tier": "huge", "needs_human": false}', None),
            ('{"tier": "mid"}', None),
            ("I think mid.", None),
        ],
    )
    def test_only_complete_valid_answers_parse(self, content, expected):
        assert parse_answers(content, ROUTE) == expected


@pytest.mark.unit
class TestBaselineLLM:
    def test_reports_the_usage_the_endpoint_returned(self):
        llm, sent = _llm(['{"tier": "mid", "needs_human": false}'], 321, 12)
        answer = llm.ask({"task": "x"}, ROUTE)
        assert (answer.prompt_tokens, answer.completion_tokens) == (321, 12)
        assert sent[0]["temperature"] == 0
        assert json.loads(sent[0]["messages"][1]["content"])["state"] == {"task": "x"}

    def test_an_empty_url_fails_loud(self):
        with pytest.raises(ImproperlyConfigured, match="DECISION_BASELINE_LLM_URL"):
            BaselineLLM(url="", model="m").ask({}, ROUTE)

    def test_a_rejected_key_fails_loud(self):
        llm, _ = _llm(["{}"], status=401)
        with pytest.raises(ImproperlyConfigured, match="API_KEY"):
            llm.ask({}, ROUTE)


@pytest.mark.unit
class TestSavings:
    def test_hybrid_sends_only_escalated_items_to_the_llm(self, settings):
        settings.DECISION_LLM_INPUT_PRICE_PER_MTOK = 3.0
        settings.DECISION_LLM_OUTPUT_PRICE_PER_MTOK = 15.0
        DecisionService._providers["fake"] = _Confidences([0.9, 0.9, 0.2])
        llm, _ = _llm(
            [
                '{"tier": "local", "needs_human": false}',
                '{"tier": "mid", "needs_human": false}',
                '{"tier": "frontier", "needs_human": false}',
            ],
            prompt_tokens=1000,
            completion_tokens=100,
        )
        items = [
            FlowItem("a", {"task": "a"}, {"tier": "local", "needs_human": False}),
            FlowItem("b", {"task": "b"}, {"tier": "local", "needs_human": False}),
            FlowItem("c", {"task": "c"}, {"tier": "frontier", "needs_human": False}),
        ]
        service = DecisionSavingsService(provider="fake", baseline=llm)
        data = service.measure("route_task", items, "test").as_dict()
        assert (data["resolved_locally"], data["local_rate"]) == (
            2,
            pytest.approx(2 / 3),
        )
        assert data["tokens"]["llm_only"] == {"prompt": 3000, "completion": 300}
        assert data["tokens"]["hybrid"] == {"prompt": 1000, "completion": 100}
        assert data["tokens"]["saved"] == 2200
        assert data["cost_usd"]["llm_only"] == pytest.approx(0.0135)
        assert data["cost_usd"]["hybrid"] == pytest.approx(0.0045)
        # The LLM said "mid" for b, the engine said "local": 3 of 4 agree.
        assert data["agreement_on_local"] == pytest.approx(0.75)
        assert data["accuracy"] == {
            "llm_only": pytest.approx(5 / 6),
            "hybrid": pytest.approx(1.0),
        }

    def test_only_escalated_questions_go_to_the_llm(self):
        DecisionService._providers["fake"] = _Confidences(
            [{"tier": 0.2, "needs_human": 0.9}]
        )
        llm, sent = _llm(
            ['{"tier": "mid", "needs_human": false}', '{"tier": "mid"}'],
            prompt_tokens=500,
            completion_tokens=5,
        )
        item = FlowItem("a", {"task": "a"}, {"tier": "mid", "needs_human": False})
        data = (
            DecisionSavingsService(provider="fake", baseline=llm)
            .measure("route_task", [item], "test")
            .as_dict()
        )
        subset = json.loads(sent[1]["messages"][1]["content"])["questions"]
        assert list(subset) == ["tier"]
        assert (data["resolved_locally"], data["local_answer_share"]) == (0, 0.5)
        assert data["accuracy"]["hybrid"] == 1.0
        assert data["agreement_on_local"] == 1.0

    def test_cost_is_absent_without_prices(self):
        DecisionService._providers["fake"] = _Confidences([0.9])
        llm, _ = _llm(['{"tier": "local", "needs_human": false}'])
        data = (
            DecisionSavingsService(provider="fake", baseline=llm)
            .measure("route_task", [FlowItem("a", {"task": "a"})], "test")
            .as_dict()
        )
        assert data["cost_usd"] == {"llm_only": None, "hybrid": None}
        assert data["accuracy"] == {"llm_only": None, "hybrid": None}


@pytest.mark.unit
def test_roadmap_rows_become_tasks(tmp_path):
    path = tmp_path / "ROADMAP.md"
    path.write_text(
        "| # | Feature | Priority | Description |\n"
        "|---|---------|----------|-------------|\n"
        "| 3.1 | **BulkAPIMixin** | P0 | Mixin for bulk writes. |\n"
        "Some prose | not a row |\n"
    )
    (item,) = roadmap_tasks(path)
    assert item.state == {"task": "BulkAPIMixin: Mixin for bulk writes."}
