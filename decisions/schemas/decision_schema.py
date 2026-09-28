"""Schemas for the decisions API.

Request and response shapes for ``POST /decisions/evaluate``, plus the
fixture schemas used by the admin and the seed command.

Question types use Laya's vocabulary. ``noul`` is the engine's name for a
yes/no question; it is not a typo for ``null``.
"""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from core.schemas.base_schema import CamelCaseSchema

#: Question types the engine understands. These are Laya's typed-question
#: names and are sent to the engine unchanged.
QuestionType = Literal["choice", "score", "noul"]


class QuestionSchema(CamelCaseSchema):
    """A single question the engine must answer.

    Attributes:
        type: Question kind. ``choice`` picks a label, ``score`` returns a
            number, ``noul`` returns a yes probability (or a fake boolean).
        instructions: Human-readable instruction for the question.
        criteria: Allowed labels for a ``choice`` question, or a mapping of
            label to description. ``score`` questions may use a list of
            anchor descriptions.
    """

    type: QuestionType
    instructions: str
    criteria: dict[str, str] | list[str] | None = None


class DecisionRequestSchema(CamelCaseSchema):
    """Payload for ``POST /decisions/evaluate``.

    The server selects the provider from ``SYSTEMONE_PROVIDER``. Callers
    cannot choose one, so an API user cannot pick ``fake`` or bypass the
    configured engine. Unknown fields, including ``provider``, are rejected.

    Attributes:
        state: Structured input the engine reasons over.
        questions: Questions to answer, keyed by question name.
    """

    model_config = ConfigDict(extra="forbid")

    state: dict[str, Any]
    questions: dict[str, QuestionSchema]


class DecisionResponseSchema(CamelCaseSchema):
    """Result of a decision request.

    Attributes:
        answers: Answer value per question key.
        answer_confidence: Provider confidence per question key.
        confidence: Aggregate confidence for the request: the lowest
            per-answer confidence, so one weak answer holds the result back.
        provider: Name of the provider that answered.
        routing: Provider routing metadata, when the provider reports it.
        fallback_used: Whether a non-primary provider answered.
        escalation_recommended: Whether the result should be escalated. Set by
            the provider, or by the service when confidence is below
            ``DECISION_ESCALATION_THRESHOLD``.
    """

    answers: dict[str, Any]
    answer_confidence: dict[str, float]
    confidence: float
    provider: str
    routing: dict[str, Any] | None = None
    fallback_used: bool = False
    escalation_recommended: bool = False


class SimilarFixturesRequestSchema(CamelCaseSchema):
    """Payload for ``POST /decisions/similar``.

    Attributes:
        text: The new case, as plain text.
        kind: Optional fixture kind to search within.
        limit: Number of nearest fixtures to return.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=8000)
    kind: Literal["support_ticket", "form_submission", "api_payload"] | None = None
    limit: int = Field(5, ge=1, le=20)


class SimilarFixtureSchema(CamelCaseSchema):
    """A stored fixture and its cosine distance to the query (0 is identical)."""

    id: str
    kind: str
    name: str
    description: str
    payload: dict[str, Any]
    distance: float
