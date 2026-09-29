"""Schemas for the agent decision endpoints under ``/decisions/agent``.

Every request schema forbids extra fields, so a caller cannot pick the
provider or send a threshold. The server uses ``SYSTEMONE_PROVIDER`` and
``DECISION_THRESHOLDS_FILE``.
"""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from core.schemas.base_schema import CamelCaseSchema


class RouteTaskSchema(CamelCaseSchema):
    """A coding task to route to a model tier."""

    model_config = ConfigDict(extra="forbid")

    task: str = Field(..., min_length=1, max_length=8000)
    files_hint: str = Field("", max_length=2000)


class TriageChangeSchema(CamelCaseSchema):
    """A pull request or commit to triage."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field("", max_length=8000)
    files: list[str] = Field(default_factory=list, max_length=200)
    additions: int = Field(0, ge=0)
    deletions: int = Field(0, ge=0)


class GateActionSchema(CamelCaseSchema):
    """An action an agent wants to run."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., min_length=1, max_length=4000)
    environment: Literal["local", "ci", "staging", "production"] = "local"
    reason: str = Field("", max_length=2000)


class PickGeneratorSchema(CamelCaseSchema):
    """A feature request to match to a ``generate_feature`` generator."""

    model_config = ConfigDict(extra="forbid")

    request: str = Field(..., min_length=1, max_length=4000)
    app_name: str = Field("", max_length=40, pattern=r"^([a-z][a-z0-9_]*)?$")


class AgentDecisionSchema(CamelCaseSchema):
    """A pack's typed answers and the step they lead to.

    Attributes:
        pack: The question pack that was asked.
        provider: The provider that answered.
        next_step: What the caller should do next. ``escalate`` means the
            local answer was too weak: use a stronger model or a person.
        resolved_locally: Whether every answer met its threshold.
        answers: Answer per question key.
        answer_confidence: Provider confidence per question key.
        escalated_questions: Question keys below their threshold.
        details: Step details, such as review reasons or a generator command.
    """

    pack: str
    provider: str
    next_step: str
    resolved_locally: bool
    answers: dict[str, Any]
    answer_confidence: dict[str, float]
    escalated_questions: list[str]
    details: dict[str, Any]
