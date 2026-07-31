import logging

from django.http import HttpRequest
from ninja_extra import api_controller, http_get, http_post
from ninja_jwt.authentication import JWTAuth

from api.decorators import handle_exceptions
from billing.schemas import (
    CheckoutSessionResponseSchema,
    CreateCheckoutSessionSchema,
    CustomerPortalResponseSchema,
    CustomerPortalSchema,
    PlanSchema,
    SubscriptionSchema,
)
from billing.services import BillingService
from billing.webhooks import handle_stripe_webhook

logger = logging.getLogger(__name__)


@api_controller("/billing", tags=["Billing"], auth=JWTAuth())
class BillingController:
    def __init__(self):
        self.service = BillingService()

    @http_get("/plans", response={200: list[PlanSchema]}, auth=None)
    def list_plans(self, request):
        return 200, self.service.list_plans()

    @http_get("/subscription", response={200: SubscriptionSchema, 404: dict})
    def get_subscription(self, request):
        subscription = self.service.get_active_subscription(request.user)
        if subscription is None:
            return 404, {"detail": "No active subscription found"}
        return 200, subscription

    @http_post(
        "/checkout", response={200: CheckoutSessionResponseSchema, 400: dict, 404: dict}
    )
    @handle_exceptions()
    def create_checkout_session(self, request, payload: CreateCheckoutSessionSchema):
        result = self.service.create_checkout_session(
            user=request.user,
            plan_id=payload.plan_id,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
        )
        return 200, CheckoutSessionResponseSchema(
            session_id=result["session_id"],
            checkout_url=result["checkout_url"],
        )

    @http_post(
        "/portal", response={200: CustomerPortalResponseSchema, 400: dict, 404: dict}
    )
    @handle_exceptions()
    def create_customer_portal(self, request, payload: CustomerPortalSchema):
        result = self.service.create_customer_portal(
            user=request.user,
            return_url=payload.return_url,
        )
        return 200, CustomerPortalResponseSchema(portal_url=result["portal_url"])


@api_controller("/billing/webhooks", tags=["Billing"])
class StripeWebhookController:
    @http_post("/stripe", response={200: dict, 400: dict}, auth=None)
    @handle_exceptions()
    def stripe_webhook(self, request: HttpRequest):
        response = handle_stripe_webhook(request)
        if response.status_code == 200:
            return 200, {"status": "ok"}
        return 400, {"detail": "Webhook error"}
