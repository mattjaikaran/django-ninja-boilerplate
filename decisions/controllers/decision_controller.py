"""Decision controller — the HTTP adapter for the decision engine.

The controller validates input, delegates to :class:`DecisionService`, and
returns a response schema. It holds no business logic.

Route prefix: /decisions. Registered only when ``ENABLE_DECISIONS`` is true.
"""

import logging

from django.core.exceptions import ImproperlyConfigured
from ninja_extra import api_controller, http_post
from ninja_extra.throttling import DynamicRateThrottle
from ninja_jwt.authentication import JWTAuth

from api.decorators import log_api_call, validate_request
from api.exceptions import ValidationError
from decisions.schemas import DecisionRequestSchema, DecisionResponseSchema
from decisions.services import DecisionService

logger = logging.getLogger(__name__)


@api_controller("/decisions", tags=["Decisions"], auth=JWTAuth())
class DecisionController:
    """HTTP adapter for the System One decision engine."""

    def __init__(self) -> None:
        """Initialise the controller with an injected service."""
        self.service = DecisionService()

    @http_post(
        "/evaluate",
        response={200: DecisionResponseSchema, 400: dict, 500: dict},
        throttle=DynamicRateThrottle(scope="decisions"),
    )
    @log_api_call(include_payload=True, include_response=False)
    @validate_request()
    def evaluate(self, request, payload: DecisionRequestSchema):
        """Answer the supplied questions from the supplied state.

        Args:
            request: The HTTP request object.
            payload: Validated decision request.

        Returns:
            Tuple of (200, result) with the provider's answers. Returns
            (400, error) for an unknown provider and (500, error) with the
            install instructions when a provider is unavailable.
        """
        try:
            result = self.service.decide(
                state=payload.state,
                questions=payload.questions,
                provider=payload.provider,
            )
        except ValidationError as exc:
            return 400, {"error": exc.code, "message": exc.message}
        except ImproperlyConfigured as exc:
            logger.error("Decision provider unavailable: %s", exc)
            return 500, {"error": "provider_unavailable", "message": str(exc)}
        return 200, DecisionResponseSchema.model_validate(result)
