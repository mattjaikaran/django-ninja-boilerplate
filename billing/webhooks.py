import logging

import stripe
from django.conf import settings
from django.http import HttpRequest, HttpResponse

# Import the exception class directly so that mocking stripe.Webhook doesn't
# break the except clause (mock objects aren't valid exception classes).
from stripe import SignatureVerificationError as StripeSignatureError

from billing.services import BillingService

logger = logging.getLogger(__name__)

billing_service = BillingService()


def handle_stripe_webhook(request: HttpRequest) -> HttpResponse:
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except StripeSignatureError:
        logger.warning("Invalid Stripe webhook signature")
        return HttpResponse(status=400)
    except Exception as exc:
        logger.exception("Error constructing Stripe event: %s", exc)
        return HttpResponse(status=400)

    event_type = event["type"]
    event_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        billing_service.handle_checkout_completed(event_object)
    elif event_type == "invoice.payment_failed":
        billing_service.handle_invoice_payment_failed(event_object)
    elif event_type == "customer.subscription.deleted":
        billing_service.handle_subscription_deleted(event_object)
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return HttpResponse(status=200)
