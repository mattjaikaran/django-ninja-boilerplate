from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from billing.models import Plan, Subscription
from core.tests.factories import UserFactory

User = get_user_model()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def auth_headers(user):
    from ninja_jwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.fixture
def plan(db):
    return Plan.objects.create(
        name="Pro",
        description="Pro plan",
        stripe_price_id="price_test_123",
        stripe_product_id="prod_test_123",
        amount="9.99",
        currency="usd",
        interval="month",
        features=["feature_a", "feature_b"],
        is_active=True,
    )


@pytest.fixture
def inactive_plan(db):
    return Plan.objects.create(
        name="Legacy",
        stripe_price_id="price_legacy_456",
        amount="4.99",
        is_active=False,
    )


@pytest.fixture
def subscription(db, user, plan):
    return Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_test_123",
        stripe_customer_id="cus_test_123",
        status="active",
    )


@pytest.mark.django_db
class TestPlanModel:
    def test_is_free_false_for_paid_plan(self, plan):
        assert not plan.is_free

    def test_is_free_true_for_zero_amount(self, db):
        free_plan = Plan.objects.create(
            name="Free",
            stripe_price_id="price_free",
            amount="0.00",
            is_active=True,
        )
        assert free_plan.is_free

    def test_str(self, plan):
        assert str(plan) == "Pro (month)"

    def test_active_filter(self, plan, inactive_plan):
        active = Plan.objects.filter(is_active=True)
        assert plan in active
        assert inactive_plan not in active


@pytest.mark.django_db
class TestSubscriptionModel:
    def test_is_active_when_active(self, subscription):
        assert subscription.is_active

    def test_is_active_when_trialing(self, subscription):
        subscription.status = "trialing"
        subscription.save()
        assert subscription.is_active

    def test_not_active_when_canceled(self, subscription):
        subscription.status = "canceled"
        subscription.save()
        assert not subscription.is_active

    def test_str(self, subscription, user, plan):
        assert str(user) in str(subscription)
        assert str(plan) in str(subscription)


@pytest.mark.django_db
class TestListPlansEndpoint:
    def test_list_plans_no_auth_required(self, plan, inactive_plan):
        client = Client()
        response = client.get("/api/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        ids = [p["stripe_price_id"] for p in data]
        assert "price_test_123" in ids
        assert "price_legacy_456" not in ids

    def test_list_plans_returns_active_only(self, plan, inactive_plan):
        client = Client()
        response = client.get("/api/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert all(p["is_active"] for p in data)

    def test_plan_schema_includes_is_free(self, plan):
        client = Client()
        response = client.get("/api/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert "is_free" in data[0]


@pytest.mark.django_db
class TestGetSubscriptionEndpoint:
    def test_returns_404_when_no_subscription(self, user, auth_headers):
        client = Client()
        response = client.get("/api/billing/subscription", **auth_headers)
        assert response.status_code == 404

    def test_returns_subscription_when_active(self, user, auth_headers, subscription):
        client = Client()
        response = client.get("/api/billing/subscription", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["stripe_subscription_id"] == "sub_test_123"
        assert data["status"] == "active"
        assert "plan" in data
        assert data["plan"]["name"] == "Pro"

    def test_requires_auth(self):
        client = Client()
        response = client.get("/api/billing/subscription")
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestCheckoutEndpoint:
    def test_checkout_requires_auth(self, plan):
        client = Client()
        payload = {
            "plan_id": str(plan.id),
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        }
        response = client.post(
            "/api/billing/checkout",
            data=payload,
            content_type="application/json",
        )
        assert response.status_code in (401, 403)

    def test_checkout_returns_400_when_stripe_not_configured(
        self, user, auth_headers, plan, settings
    ):
        settings.STRIPE_SECRET_KEY = ""
        client = Client()
        payload = {
            "plan_id": str(plan.id),
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        }
        response = client.post(
            "/api/billing/checkout",
            data=payload,
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 400

    def test_checkout_returns_404_for_unknown_plan(self, user, auth_headers, settings):
        settings.STRIPE_SECRET_KEY = "sk_test_fake"
        client = Client()
        payload = {
            "plan_id": "00000000-0000-0000-0000-000000000000",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        }
        response = client.post(
            "/api/billing/checkout",
            data=payload,
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 404

    @patch("billing.services.billing_service.stripe")
    def test_checkout_success(self, mock_stripe, user, auth_headers, plan, settings):
        settings.STRIPE_SECRET_KEY = "sk_test_fake"
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/pay/cs_test_123"
        mock_stripe.checkout.Session.create.return_value = mock_session

        client = Client()
        payload = {
            "plan_id": str(plan.id),
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        }
        response = client.post(
            "/api/billing/checkout",
            data=payload,
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "cs_test_123"
        assert "checkout_url" in data


@pytest.mark.django_db
class TestWebhookController:
    def test_webhook_endpoint_exists(self):
        client = Client()
        response = client.post(
            "/api/billing/webhooks/stripe",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=0,v1=fake",
        )
        assert response.status_code in (200, 400)

    @patch("billing.webhooks.stripe")
    def test_webhook_rejects_invalid_signature(self, mock_stripe):
        import stripe as real_stripe

        mock_stripe.Webhook.construct_event.side_effect = (
            real_stripe.error.SignatureVerificationError(
                "Invalid signature", "fake_sig"
            )
        )
        client = Client()
        response = client.post(
            "/api/billing/webhooks/stripe",
            data=b'{"type": "checkout.session.completed"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=0,v1=badsig",
        )
        assert response.status_code == 400

    @patch("billing.webhooks.billing_service")
    @patch("billing.webhooks.stripe")
    def test_webhook_routes_checkout_completed(self, mock_stripe, mock_service):
        mock_event = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test"}},
        }
        mock_stripe.Webhook.construct_event.return_value = mock_event

        client = Client()
        response = client.post(
            "/api/billing/webhooks/stripe",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=0,v1=valid",
        )
        assert response.status_code == 200
        mock_service.handle_checkout_completed.assert_called_once()

    @patch("billing.webhooks.billing_service")
    @patch("billing.webhooks.stripe")
    def test_webhook_routes_payment_failed(self, mock_stripe, mock_service):
        mock_event = {
            "type": "invoice.payment_failed",
            "data": {"object": {"subscription": "sub_123"}},
        }
        mock_stripe.Webhook.construct_event.return_value = mock_event

        client = Client()
        response = client.post(
            "/api/billing/webhooks/stripe",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=0,v1=valid",
        )
        assert response.status_code == 200
        mock_service.handle_invoice_payment_failed.assert_called_once()

    @patch("billing.webhooks.billing_service")
    @patch("billing.webhooks.stripe")
    def test_webhook_routes_subscription_deleted(self, mock_stripe, mock_service):
        mock_event = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_123"}},
        }
        mock_stripe.Webhook.construct_event.return_value = mock_event

        client = Client()
        response = client.post(
            "/api/billing/webhooks/stripe",
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=0,v1=valid",
        )
        assert response.status_code == 200
        mock_service.handle_subscription_deleted.assert_called_once()
