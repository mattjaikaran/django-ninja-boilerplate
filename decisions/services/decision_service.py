"""Business logic for the decisions app.

:class:`DecisionService` is the single entry point for callers. It selects a
provider from the ``SYSTEMONE_PROVIDER`` setting (or the constructor argument
for internal callers), caches provider instances, and applies the escalation
policy.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar

from django.conf import settings
from pydantic import BaseModel

from api.exceptions import ValidationError
from decisions.models import DecisionFixture
from decisions.providers import PROVIDER_REGISTRY, DecisionProvider, DecisionResult

logger = logging.getLogger(__name__)

#: Results below this aggregate confidence are flagged for escalation.
DEFAULT_ESCALATION_THRESHOLD = 0.5


class DecisionService:
    """Facade over the configured System One decision provider."""

    #: Provider instances, keyed by name. Providers are stateless across
    #: requests, so one instance per name is reused for the process lifetime.
    _providers: ClassVar[dict[str, DecisionProvider]] = {}

    def __init__(self, provider: str | None = None) -> None:
        """Initialise the service.

        Args:
            provider: Provider name to use by default. Falls back to the
                ``SYSTEMONE_PROVIDER`` setting.
        """
        self._provider_name = provider or getattr(
            settings, "SYSTEMONE_PROVIDER", "laya"
        )

    @property
    def provider_name(self) -> str:
        """Return the provider name this service uses by default."""
        return self._provider_name

    # ------------------------------------------------------------------
    # Provider selection
    # ------------------------------------------------------------------

    def get_provider(self, name: str | None = None) -> DecisionProvider:
        """Return the provider instance for *name*.

        Instances are created once and cached on the class.

        Args:
            name: Provider name. Defaults to the service's provider.

        Returns:
            The cached provider instance.

        Raises:
            ValidationError: If *name* is not a registered provider.
        """
        resolved = (name or self._provider_name).lower()
        provider = self._providers.get(resolved)
        if provider is None:
            provider_cls = PROVIDER_REGISTRY.get(resolved)
            if provider_cls is None:
                raise ValidationError(
                    f"Unknown decision provider '{resolved}'. "
                    f"Available providers: {', '.join(sorted(PROVIDER_REGISTRY))}.",
                )
            provider = provider_cls()
            self._providers[resolved] = provider
        return provider

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def decide(
        self,
        state: dict[str, Any],
        questions: dict[str, Any],
    ) -> DecisionResult:
        """Answer *questions* using *state* with this service's provider.

        Args:
            state: Structured input for the decision.
            questions: Mapping of question key to a question definition.

        Returns:
            The provider's :class:`DecisionResult`, with the escalation policy
            applied.

        Raises:
            ValidationError: If the provider name is unknown.
            ImproperlyConfigured: If the selected provider is unavailable.
        """
        # The HTTP layer validates QuestionSchema objects; provider wire APIs
        # need plain mappings. Keep direct service callers' dicts unchanged.
        wire_questions = {
            key: question.model_dump(exclude_none=True)
            if isinstance(question, BaseModel)
            else question
            for key, question in questions.items()
        }
        result = self.get_provider().predict(state, wire_questions)
        return self._apply_escalation_policy(result)

    def _apply_escalation_policy(self, result: DecisionResult) -> DecisionResult:
        """Flag weak results for escalation.

        A provider may set ``escalation_recommended`` itself; otherwise the
        result is escalated when it has answers and its aggregate confidence
        falls below ``DECISION_ESCALATION_THRESHOLD``. A request with no
        questions is empty, not weak, so it is never escalated.

        Args:
            result: The provider result.

        Returns:
            The result, flagged for escalation when it is too weak.
        """
        if result.escalation_recommended or not result.answers:
            return result
        threshold = float(
            getattr(
                settings, "DECISION_ESCALATION_THRESHOLD", DEFAULT_ESCALATION_THRESHOLD
            )
        )
        if result.confidence >= threshold:
            return result
        return replace(result, escalation_recommended=True)

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    def list_fixtures(self, kind: str | None = None) -> Any:
        """Return stored decision fixtures.

        Args:
            kind: Optional fixture kind to filter on.

        Returns:
            A queryset of :class:`DecisionFixture` ordered by kind and name.
        """
        queryset = DecisionFixture.objects.all()
        if kind:
            queryset = queryset.filter(kind=kind)
        return queryset.order_by("kind", "name")

    def seed_fixtures(self, fixtures_dir: Path) -> dict[str, int]:
        """Load every JSON fixture file in *fixtures_dir*.

        The operation is idempotent: a fixture with the same ``kind`` and
        ``name`` is updated in place, not duplicated. A stored embedding is
        kept when the text it was computed from is unchanged, and cleared when
        the description or payload changes, so ``embed_decisions`` recomputes
        only stale vectors. A file may supply its own ``embedding``.

        Args:
            fixtures_dir: Directory holding the ``*.json`` fixture files.

        Returns:
            Counts of created and updated rows.

        Raises:
            ValueError: If a fixture file has no ``kind`` key.
        """
        created = 0
        updated = 0
        for path in sorted(fixtures_dir.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            kind = document.get("kind")
            if not kind:
                raise ValueError(f"Fixture file {path.name} is missing a 'kind' key.")
            for item in document.get("fixtures", []):
                description = item.get("description", "")
                payload = item.get("payload", {})
                fixture, was_created = DecisionFixture.objects.get_or_create(
                    kind=kind,
                    name=item["name"],
                    defaults={"description": description, "payload": payload},
                )
                changed = (fixture.description, fixture.payload) != (
                    description,
                    payload,
                )
                fixture.description = description
                fixture.payload = payload
                if item.get("embedding") is not None:
                    fixture.embedding = item["embedding"]
                elif changed:
                    fixture.embedding = None
                fixture.save()
                created += int(was_created)
                updated += int(not was_created)
        logger.info(
            "Seeded decision fixtures: %s created, %s updated", created, updated
        )
        return {"created": created, "updated": updated}
