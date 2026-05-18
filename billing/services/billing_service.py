import logging
from datetime import UTC, datetime
from typing import Any

import stripe
from django.conf import settings
from django.utils import timezone
from ninja.errors import HttpError

from billing.models import Plan, Subscription

logger = logging.getLogger(__name__)


class BillingService:
    def _require_stripe(self) -> None:
        if not settings.STRIPE_SECRET_KEY:
            raise HttpError(400, "Stripe not configured")
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def list_plans(self) -> list[Plan]:
        return list(Plan.objects.filter(is_active=True))

    def get_active_subscription(self, user: Any) -> Subscription | None:
        return (
            Subscription.objects.select_related("plan")
            .filter(user=user, status__in=("active", "trialing"))
            .order_by("-created_at")
            .first()
        )

    def create_checkout_session(
        self,
        user: Any,
        plan_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        self._require_stripe()

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist as err:
            raise HttpError(404, "Plan not found") from err

        session = stripe.checkout.Session.create(
            customer_email=user.email,
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": str(user.id), "plan_id": str(plan.id)},
        )

        return {"session_id": session.id, "checkout_url": session.url}

    def create_customer_portal(self, user: Any, return_url: str) -> dict:
        self._require_stripe()

        subscription = self.get_active_subscription(user)
        if not subscription or not subscription.stripe_customer_id:
            raise HttpError(404, "No active subscription found")

        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
        )

        return {"portal_url": session.url}

    def handle_checkout_completed(self, session: Any) -> None:
        stripe_subscription_id = session.get("subscription")
        stripe_customer_id = session.get("customer")
        metadata = session.get("metadata", {})

        user_id = metadata.get("user_id")
        plan_id = metadata.get("plan_id")

        if not all([stripe_subscription_id, stripe_customer_id, user_id, plan_id]):
            logger.warning(
                "checkout.session.completed missing required metadata: %s", metadata
            )
            return

        try:
            plan = Plan.objects.get(id=plan_id)
        except Plan.DoesNotExist:
            logger.error("Plan %s not found during checkout completion", plan_id)
            return

        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger.error("User %s not found during checkout completion", user_id)
            return

        stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)

        Subscription.objects.update_or_create(
            stripe_subscription_id=stripe_subscription_id,
            defaults={
                "user": user,
                "plan": plan,
                "stripe_customer_id": stripe_customer_id,
                "status": stripe_sub.status,
                "current_period_start": datetime.fromtimestamp(
                    stripe_sub.current_period_start, tz=UTC
                ),
                "current_period_end": datetime.fromtimestamp(
                    stripe_sub.current_period_end, tz=UTC
                ),
            },
        )
        logger.info("Subscription created/updated for user %s", user_id)

    def handle_invoice_payment_failed(self, invoice: Any) -> None:
        stripe_subscription_id = invoice.get("subscription")
        if not stripe_subscription_id:
            return

        updated = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).update(status="past_due")

        if updated:
            logger.info("Marked subscription %s as past_due", stripe_subscription_id)

    def handle_subscription_deleted(self, subscription_data: Any) -> None:
        stripe_subscription_id = subscription_data.get("id")
        if not stripe_subscription_id:
            return

        updated = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).update(status="canceled", canceled_at=timezone.now())

        if updated:
            logger.info("Marked subscription %s as canceled", stripe_subscription_id)
