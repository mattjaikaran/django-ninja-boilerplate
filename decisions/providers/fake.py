"""Deterministic provider for tests and local development.

The fake provider never loads a model and never touches the network. Given
the same input it always returns the same answer, which makes it safe for
unit tests and for local smoke checks.
"""

from __future__ import annotations

from typing import Any

from decisions.providers.base import (
    DecisionProvider,
    DecisionResult,
    aggregate_confidence,
)

#: Answer for a ``choice`` question when no criteria are supplied.
DEFAULT_CHOICE = "approve"

#: Answer for a ``score`` question.
DEFAULT_SCORE = 1.0

#: Answer for a ``noul`` question.
DEFAULT_NOUL = False


def _field(question: Any, name: str) -> Any:
    """Return *name* from a question definition, mapping or object."""
    if isinstance(question, dict):
        return question.get(name)
    return getattr(question, name, None)


class FakeProvider(DecisionProvider):
    """Deterministic provider with no external dependencies."""

    name = "fake"

    def __init__(self, confidence: float = 0.99) -> None:
        """Initialise the provider.

        Args:
            confidence: Confidence reported for every answer.
        """
        self.confidence = confidence

    def is_available(self) -> bool:
        """Return ``True``; the fake provider is always available."""
        return True

    def predict(
        self,
        state: dict[str, Any],
        questions: dict[str, Any],
    ) -> DecisionResult:
        """Return a deterministic answer for every question.

        ``choice`` questions return the first criterion label (or
        :data:`DEFAULT_CHOICE`), ``score`` questions return
        :data:`DEFAULT_SCORE`, and ``noul`` questions return
        :data:`DEFAULT_NOUL`.

        Args:
            state: Ignored; accepted for interface compatibility.
            questions: Mapping of question key to a question definition.

        Returns:
            A :class:`DecisionResult` with one answer per question.
        """
        answers: dict[str, Any] = {}
        for key, question in questions.items():
            qtype = _field(question, "type")
            if qtype == "choice":
                criteria = _field(question, "criteria")
                if isinstance(criteria, dict) and criteria:
                    answers[key] = next(iter(criteria))
                elif isinstance(criteria, list) and criteria:
                    answers[key] = criteria[0]
                else:
                    answers[key] = DEFAULT_CHOICE
            elif qtype == "score":
                answers[key] = DEFAULT_SCORE
            elif qtype == "noul":
                answers[key] = DEFAULT_NOUL
            else:
                answers[key] = None

        confidences = dict.fromkeys(answers, self.confidence)
        return DecisionResult(
            answers=answers,
            answer_confidence=confidences,
            confidence=aggregate_confidence(confidences.values()),
            provider=self.name,
        )
