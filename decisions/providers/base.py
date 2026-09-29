"""Provider abstraction for the System One decision engine.

A *provider* answers a set of questions from a piece of state. The
boilerplate ships three:

``fake``
    Deterministic answers for tests. No model loading, no network.
``laya``
    The in-process Laya System 1 engine (default).
``jev``
    The hosted TypeSafe ("Jev") API.

Laya answers each question with a typed value *and its own confidence*, and
reports which checkpoint handled the request::

    {
        "answers": {
            "department": {"choice": "billing", "confidence": 0.94},
            "urgency": {"score": 0.8, "confidence": 0.71},
            "churn_risk": {"noul": True, "confidence": 0.88},
        },
        "routing": {"model": "english", "repo": "...", "reason": "..."},
    }

Every provider normalises its response to a :class:`DecisionResult`, so
callers never depend on a vendor's response shape.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

#: Keys a provider may use to carry a question's value inside an answer entry.
#: These are Laya's typed-question names, which the Jev-compatible API shares.
ANSWER_VALUE_KEYS = ("choice", "score", "noul", "value")


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """A provider's answer to a decision request.

    Attributes:
        answers: Answer value per question key (for example ``"billing"``,
            ``0.8``, or ``True``).
        answer_confidence: Confidence per question key, as reported by the
            provider.
        confidence: Aggregate confidence for the whole request. See
            :func:`aggregate_confidence` for the policy.
        provider: Name of the provider that produced the result.
        routing: Provider routing metadata, or ``None`` when the provider
            does not report it.
        fallback_used: Whether a non-primary provider answered the request.
        escalation_recommended: Whether the result is too weak to trust and
            should be escalated to a human.
        escalated_questions: Question keys whose confidence fell below their
            escalation threshold.
    """

    answers: dict[str, Any]
    answer_confidence: dict[str, float]
    confidence: float
    provider: str
    routing: dict[str, Any] | None = None
    fallback_used: bool = False
    escalation_recommended: bool = False
    escalated_questions: tuple[str, ...] = ()


def aggregate_confidence(confidences: Iterable[float]) -> float:
    """Reduce per-answer confidences to one number.

    The policy is the **minimum**: a decision is only as trustworthy as its
    weakest answer, so one low-confidence answer holds the whole result back.
    An empty request has no confidence, so it returns ``0.0``.

    Args:
        confidences: Per-answer confidence values.

    Returns:
        The lowest confidence, or ``0.0`` when there are none.
    """
    values = list(confidences)
    return min(values) if values else 0.0


def _reader(raw: Any):
    """Return a key accessor for a mapping or an arbitrary object."""
    if isinstance(raw, Mapping):
        return raw.get
    return lambda key, default=None: getattr(raw, key, default)


def _split_answer(entry: Any) -> tuple[Any, float]:
    """Split a mapping or typed SDK answer into its value and confidence.

    Noul is a probability of yes, not a confidence score. For SDK answers
    without a confidence field, use the probability of the selected side.
    """
    if not isinstance(entry, Mapping):
        for key in ANSWER_VALUE_KEYS:
            if hasattr(entry, key):
                value = getattr(entry, key)
                confidence = getattr(entry, "confidence", None)
                if confidence is None and key == "noul":
                    confidence = max(float(value), 1.0 - float(value))
                return value, float(confidence) if confidence is not None else 0.0
        return entry, 0.0
    confidence = entry.get("confidence")
    if confidence is None and "noul" in entry:
        probability = float(entry["noul"])
        confidence = max(probability, 1.0 - probability)
    confidence = float(confidence) if confidence is not None else 0.0
    for key in ANSWER_VALUE_KEYS:
        if key in entry:
            return entry[key], confidence
    # Unknown shape: keep the entry, but not the confidence already split out.
    return (
        {key: value for key, value in entry.items() if key != "confidence"},
        confidence,
    )


def result_from_raw(
    raw: Any,
    provider: str,
    *,
    fallback_used: bool = False,
) -> DecisionResult:
    """Normalise a provider response into a :class:`DecisionResult`.

    Accepts either a mapping or an object with matching attributes, so a
    vendor SDK can return its own type without an adapter class.

    Args:
        raw: The provider response.
        provider: Provider name to record when the response omits one.
        fallback_used: Default for the ``fallback_used`` flag.

    Returns:
        A :class:`DecisionResult` built from *raw*.
    """
    get = _reader(raw)
    raw_answers = get("answers", None) or {}
    answers: dict[str, Any] = {}
    confidences: dict[str, float] = {}
    for key, entry in raw_answers.items():
        value, confidence = _split_answer(entry)
        answers[key] = value
        confidences[key] = confidence

    routing = get("routing", None)
    return DecisionResult(
        answers=answers,
        answer_confidence=confidences,
        confidence=aggregate_confidence(confidences.values()),
        provider=get("provider", None) or provider,
        routing=dict(routing) if isinstance(routing, Mapping) else None,
        fallback_used=bool(get("fallback_used", fallback_used)),
        escalation_recommended=bool(get("escalation_recommended", False)),
    )


class DecisionProvider(ABC):
    """Abstract base class for decision providers.

    Subclasses must set :attr:`name` and implement :meth:`predict` and
    :meth:`is_available`.
    """

    #: Stable identifier used in settings and request payloads.
    name: str = "base"

    @abstractmethod
    def predict(
        self,
        state: dict[str, Any],
        questions: dict[str, Any],
    ) -> DecisionResult:
        """Answer *questions* using *state*.

        Args:
            state: Arbitrary structured input for the decision.
            questions: Mapping of question key to a question definition. Each
                definition is a mapping or object with at least ``type`` and
                ``instructions``.

        Returns:
            The provider's :class:`DecisionResult`.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` when the provider can serve a request.

        Returns:
            ``True`` if the provider's dependencies and configuration are
            present, otherwise ``False``.
        """
