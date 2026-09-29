"""Measure the tokens a local decision engine saves on a real flow.

For every item in a flow, the service asks one pack's questions:

1. the decision engine (``AgentDecisionService``), which costs no LLM tokens;
2. the baseline LLM (``BaselineLLM``), with every question and the state;
3. when the engine escalated some but not all questions, the baseline LLM
   again, with only the escalated questions.

Two flows are then compared, both from the LLM's reported usage:

* **LLM only**: every item and question goes to the LLM (call 2).
* **Hybrid**: questions whose answers met their threshold use the engine's
  answer. Escalated questions go to the LLM: call 3, or call 2 when every
  question escalated. An item with no escalated question costs no tokens.

When items carry labels, the report also compares the accuracy of both flows,
so a token saving that costs accuracy is visible.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.conf import settings

from decisions.services.agent_service import (
    AgentDecisionService,
    compact_state,
    pack_questions,
)
from decisions.services.eval_dataset import is_correct
from decisions.services.eval_metrics import percentile
from decisions.services.llm_baseline import BaselineAnswer, BaselineLLM

#: A ROADMAP.md table row: ``| 3.1 | **Name** | P0 | Description |``.
ROADMAP_ROW = re.compile(
    r"^\|\s*\d+\.\d+\s*\|\s*\*\*(.+?)\*\*\s*\|\s*P\d\s*\|\s*(.+?)\s*\|$"
)


@dataclass(frozen=True, slots=True)
class FlowItem:
    """One input to a flow, with optional labels."""

    item_id: str
    state: dict[str, Any]
    expected: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ItemResult:
    """The engine's and the baseline's answers for one item."""

    item: FlowItem
    next_step: str
    engine_answers: dict[str, Any]
    escalated: tuple[str, ...]
    engine_ms: float
    baseline: BaselineAnswer
    hybrid: BaselineAnswer | None

    def hybrid_answer(self, key: str) -> Any:
        """Return the hybrid flow's answer to *key*, or ``None`` if invalid."""
        if key not in self.escalated:
            return self.engine_answers[key]
        answers = self.hybrid.answers if self.hybrid else None
        return None if answers is None else answers[key]


def roadmap_tasks(path: Path) -> list[FlowItem]:
    """Return every feature row of a ROADMAP.md table as a coding task."""
    items: list[FlowItem] = []
    for line in path.read_text().splitlines():
        match = ROADMAP_ROW.match(line.strip())
        if match:
            name, description = match.groups()
            task = f"{name}: {description}"
            items.append(FlowItem(f"roadmap-{len(items) + 1}", {"task": task}))
    return items


def _share(part: float, whole: float) -> float | None:
    return part / whole if whole else None


def _as_label(question: dict[str, Any], value: Any) -> Any:
    """Turn a ``noul`` probability into a boolean so answers compare."""
    if question["type"] == "noul" and not isinstance(value, bool):
        return float(value) >= 0.5
    return value


@dataclass(slots=True)
class SavingsReport:
    """Measured tokens, cost, agreement, and accuracy for one flow."""

    pack: str
    source: str
    provider: str
    baseline_model: str
    results: list[ItemResult] = field(default_factory=list)

    def _tokens(self, hybrid: bool) -> tuple[int, int]:
        calls = [r.hybrid if hybrid else r.baseline for r in self.results]
        used = [c for c in calls if c is not None]
        return (
            sum(c.prompt_tokens for c in used),
            sum(c.completion_tokens for c in used),
        )

    def _accuracy(self, hybrid: bool) -> float | None:
        questions = pack_questions(self.pack)
        scored = []
        for r in self.results:
            for key, label in (r.item.expected or {}).items():
                if hybrid:
                    answer = r.hybrid_answer(key)
                else:
                    answer = r.baseline.answers[key] if r.baseline.answers else None
                scored.append(
                    answer is not None and is_correct(questions[key], answer, label)
                )
        return _share(sum(scored), len(scored))

    def _agreement(self) -> float | None:
        questions = pack_questions(self.pack)
        pairs = [
            _as_label(questions[key], value) == r.baseline.answers[key]
            for r in self.results
            if r.baseline.answers is not None
            for key, value in r.engine_answers.items()
            if key not in r.escalated
        ]
        return _share(sum(pairs), len(pairs))

    @staticmethod
    def _cost(tokens: tuple[int, int]) -> float | None:
        prices = (
            settings.DECISION_LLM_INPUT_PRICE_PER_MTOK,
            settings.DECISION_LLM_OUTPUT_PRICE_PER_MTOK,
        )
        if prices[0] is None or prices[1] is None:
            return None
        return (tokens[0] * prices[0] + tokens[1] * prices[1]) / 1_000_000

    def as_dict(self) -> dict[str, Any]:
        """Return the summary and per-item rows as JSON-serialisable data."""
        llm_only, hybrid = self._tokens(False), self._tokens(True)
        resolved = sum(not r.escalated for r in self.results)
        answers = sum(len(r.engine_answers) for r in self.results)
        local = answers - sum(len(r.escalated) for r in self.results)
        saved = sum(llm_only) - sum(hybrid)
        return {
            "pack": self.pack,
            "source": self.source,
            "provider": self.provider,
            "baseline_model": self.baseline_model,
            "items": len(self.results),
            "resolved_locally": resolved,
            "local_rate": _share(resolved, len(self.results)),
            "local_answer_share": _share(local, answers),
            "baseline_invalid": sum(r.baseline.answers is None for r in self.results),
            "tokens": {
                "llm_only": {"prompt": llm_only[0], "completion": llm_only[1]},
                "hybrid": {"prompt": hybrid[0], "completion": hybrid[1]},
                "saved": saved,
                "saved_share": _share(saved, sum(llm_only)),
            },
            "cost_usd": {
                "llm_only": self._cost(llm_only),
                "hybrid": self._cost(hybrid),
            },
            "agreement_on_local": self._agreement(),
            "accuracy": {
                "llm_only": self._accuracy(hybrid=False),
                "hybrid": self._accuracy(hybrid=True),
            },
            "latency_ms": {
                "engine_p50": percentile([r.engine_ms for r in self.results], 50),
                "baseline_p50": percentile(
                    [r.baseline.latency_ms for r in self.results], 50
                ),
            },
            "results": [
                {
                    "id": r.item.item_id,
                    "next_step": r.next_step,
                    "escalated": list(r.escalated),
                    "engine_answers": r.engine_answers,
                    "baseline_answers": r.baseline.answers,
                    "hybrid_answers": r.hybrid.answers if r.hybrid else None,
                    "expected": r.item.expected,
                    "baseline_tokens": r.baseline.total_tokens,
                    "hybrid_tokens": r.hybrid.total_tokens if r.hybrid else 0,
                }
                for r in self.results
            ],
        }


class DecisionSavingsService:
    """Run a flow through the engine and the baseline LLM."""

    def __init__(
        self, provider: str | None = None, baseline: BaselineLLM | None = None
    ) -> None:
        """Use *provider* (default ``SYSTEMONE_PROVIDER``) and *baseline*."""
        self.agents = AgentDecisionService(provider=provider)
        self.baseline = baseline or BaselineLLM()

    def measure(self, pack: str, items: list[FlowItem], source: str) -> SavingsReport:
        """Measure every item. Provider or LLM failures raise; nothing is skipped."""
        questions = pack_questions(pack)
        report = SavingsReport(
            pack=pack,
            source=source,
            provider=self.agents.decisions.provider_name,
            baseline_model=self.baseline.model,
        )
        for item in items:
            state = compact_state(item.state)
            started = time.perf_counter()
            decision = self.agents.ask(pack, item.state)
            engine_ms = (time.perf_counter() - started) * 1000
            report.provider = decision.provider
            baseline = self.baseline.ask(state, questions)
            escalated = decision.escalated_questions
            if not escalated:
                hybrid = None
            elif set(escalated) == set(questions):
                hybrid = baseline
            else:
                subset = {key: questions[key] for key in escalated}
                hybrid = self.baseline.ask(state, subset)
            report.results.append(
                ItemResult(
                    item=item,
                    next_step=decision.next_step,
                    engine_answers=decision.answers,
                    escalated=escalated,
                    engine_ms=engine_ms,
                    baseline=baseline,
                    hybrid=hybrid,
                )
            )
        return report
