"""Agent decision controller: typed local decisions for coding agents.

Route prefix: /decisions/agent. Registered only when ``ENABLE_DECISIONS`` is
true. The controller validates input, delegates to
:class:`AgentDecisionService`, and returns a response schema.
"""

import logging
from collections.abc import Callable

from django.core.exceptions import ImproperlyConfigured
from ninja_extra import api_controller, http_post
from ninja_extra.throttling import DynamicRateThrottle
from ninja_jwt.authentication import JWTAuth

from api.decorators import log_api_call, validate_request
from api.exceptions import ValidationError
from decisions.schemas import (
    AgentDecisionSchema,
    GateActionSchema,
    PickGeneratorSchema,
    RouteTaskSchema,
    TriageChangeSchema,
)
from decisions.services.agent_service import AgentDecision, AgentDecisionService

logger = logging.getLogger(__name__)

RESPONSES = {200: AgentDecisionSchema, 400: dict, 500: dict}


def _respond(call: Callable[[], AgentDecision]) -> tuple[int, object]:
    """Run *call* and map service errors to responses."""
    try:
        decision = call()
    except ValidationError as exc:
        return 400, {"error": exc.code, "message": exc.message}
    except ImproperlyConfigured as exc:
        logger.error("Decision provider unavailable: %s", exc)
        return 500, {"error": "provider_unavailable", "message": str(exc)}
    return 200, AgentDecisionSchema.model_validate(decision.as_dict())


@api_controller("/decisions/agent", tags=["Decisions"], auth=JWTAuth())
class AgentDecisionController:
    """HTTP adapter for agent workflow decisions."""

    def __init__(self) -> None:
        """Initialise the controller with its service."""
        self.service = AgentDecisionService()

    @http_post(
        "/route-task",
        response=RESPONSES,
        throttle=DynamicRateThrottle(scope="decisions"),
    )
    @log_api_call(include_payload=True, include_response=False)
    @validate_request()
    def route_task(self, request, payload: RouteTaskSchema):
        """Pick the cheapest capable model tier for a coding task."""
        return _respond(
            lambda: self.service.route_task(payload.task, payload.files_hint)
        )

    @http_post(
        "/triage-change",
        response=RESPONSES,
        throttle=DynamicRateThrottle(scope="decisions"),
    )
    @log_api_call(include_payload=True, include_response=False)
    @validate_request()
    def triage_change(self, request, payload: TriageChangeSchema):
        """Classify a PR or commit and choose the review depth."""
        return _respond(
            lambda: self.service.triage_change(
                payload.title,
                payload.description,
                payload.files,
                payload.additions,
                payload.deletions,
            )
        )

    @http_post(
        "/gate-action",
        response=RESPONSES,
        throttle=DynamicRateThrottle(scope="decisions"),
    )
    @log_api_call(include_payload=True, include_response=False)
    @validate_request()
    def gate_action(self, request, payload: GateActionSchema):
        """Decide whether an agent may run an action without approval."""
        return _respond(
            lambda: self.service.gate_action(
                payload.action, payload.environment, payload.reason
            )
        )

    @http_post(
        "/pick-generator",
        response=RESPONSES,
        throttle=DynamicRateThrottle(scope="decisions"),
    )
    @log_api_call(include_payload=True, include_response=False)
    @validate_request()
    def pick_generator(self, request, payload: PickGeneratorSchema):
        """Pick the generate_feature generator for a feature request."""
        return _respond(
            lambda: self.service.pick_generator(payload.request, payload.app_name)
        )
