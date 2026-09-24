"""Centrifugo real-time token endpoints.

Provides JWT tokens that clients use to authenticate with Centrifugo:
- Connection token: required to establish a WebSocket connection.
- Subscription token: required to subscribe to private channels.
"""

import logging

from ninja_extra import api_controller, http_post
from ninja_extra.throttling import UserRateThrottle, throttle

from api.centrifugo import generate_connection_token, generate_subscription_token
from api.decorators import log_api_call
from core.schemas.base_schema import CamelCaseSchema

logger = logging.getLogger(__name__)


class ConnectionTokenResponse(CamelCaseSchema):
    token: str


class SubscriptionTokenRequest(CamelCaseSchema):
    channel: str


class SubscriptionTokenResponse(CamelCaseSchema):
    token: str


@api_controller("/realtime", tags=["Realtime"])
class CentrifugoTokenController:
    """Token endpoints for Centrifugo real-time connections."""

    @http_post("/connection-token", response={200: ConnectionTokenResponse})
    @log_api_call()
    @throttle(UserRateThrottle)
    def get_connection_token(self, request):
        """Generate a connection token for the authenticated user.

        The client sends this token when connecting to Centrifugo via WebSocket.
        """
        user = request.user
        token = generate_connection_token(
            user_id=str(user.id),
            info={"username": user.username, "email": user.email},
        )
        return 200, {"token": token}

    @http_post("/subscription-token", response={200: SubscriptionTokenResponse})
    @log_api_call()
    @throttle(UserRateThrottle)
    def get_subscription_token(self, request, payload: SubscriptionTokenRequest):
        """Generate a subscription token for a specific channel.

        Required for private channels where `allow_subscribe_for_client` is false.
        """
        user = request.user
        token = generate_subscription_token(
            user_id=str(user.id),
            channel=payload.channel,
        )
        return 200, {"token": token}
