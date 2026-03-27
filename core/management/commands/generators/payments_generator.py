"""Payments feature generator with Stripe integration."""

from .base_generator import BaseGenerator


class PaymentsGenerator(BaseGenerator):
    """Generator for payments feature with Stripe integration."""

    def __init__(
        self,
        app_name: str,
        provider: str = "stripe",
        platform_type: str = "b2c",
        include_subscriptions: bool = True,
        include_webhooks: bool = True,
        minimal: bool = False,
    ):
        """Initialize the payments generator.

        Args:
            app_name: Name of the Django app to create
            provider: Payment provider (stripe, paypal, etc.)
            platform_type: Platform type (b2c, b2b, marketplace, saas)
            include_subscriptions: Whether to include subscription functionality
            include_webhooks: Whether to include webhook handling
            minimal: Whether to generate minimal version
        """
        super().__init__(app_name, minimal)
        self.provider = provider
        self.platform_type = platform_type
        self.include_subscriptions = include_subscriptions
        self.include_webhooks = include_webhooks

    def generate(self) -> None:
        """Generate the payments feature."""
        print(
            f"Generating payments feature with {self.provider} for {self.platform_type} platform..."
        )

        # Create Django app
        self.create_django_app()

        # Update dependencies
        self._update_dependencies()

        # Generate models
        self._generate_models()

        # Generate schemas
        self._generate_schemas()

        # Generate controllers
        self._generate_controllers()

        # Generate services
        self._generate_services()

        # Generate admin
        self._generate_admin()

        # Generate tests
        self._generate_tests()

        # Update settings
        self._update_settings()

        # Update URLs
        self.update_urls(self.app_name)

        # Create migrations
        self.create_migration()

        print("Payments feature generated successfully!")

    def _update_dependencies(self) -> None:
        """Update project dependencies."""
        dependencies = ["stripe>=8.0.0"]
        if not self.minimal:
            dependencies.extend(
                [
                    "celery>=5.3.0",
                    "django-celery-beat>=2.5.0",
                    "redis>=5.0.0",
                ]
            )
        self.update_pyproject_toml(dependencies)

    def _generate_models(self) -> None:
        """Generate payment models."""
        models_content = self._get_models_content()
        self.create_file(self.app_path / "models" / "payment.py", models_content)

        # Update models __init__.py
        init_content = """from .payment import Payment, PaymentMethod, PaymentIntent

__all__ = ["Payment", "PaymentMethod", "PaymentIntent"]
"""
        if self.include_subscriptions:
            init_content = """from .payment import Payment, PaymentMethod, PaymentIntent
from .subscription import Subscription, SubscriptionPlan

__all__ = ["Payment", "PaymentMethod", "PaymentIntent", "Subscription", "SubscriptionPlan"]
"""

            # Generate subscription models
            subscription_content = self._get_subscription_models_content()
            self.create_file(
                self.app_path / "models" / "subscription.py", subscription_content
            )

        self.create_file(self.app_path / "models" / "__init__.py", init_content)

    def _get_models_content(self) -> str:
        """Get the payment models content."""
        return '''"""Payment models."""

from django.db import models
from django.conf import settings
from core.models import AbstractBaseModel


class PaymentMethod(AbstractBaseModel):
    """Customer payment method."""

    TYPE_CHOICES = [
        ("card", "Credit Card"),
        ("bank_account", "Bank Account"),
        ("digital_wallet", "Digital Wallet"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_methods"
    )
    stripe_payment_method_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    last_four = models.CharField(max_length=4, blank=True)
    brand = models.CharField(max_length=50, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Payment Method"
        verbose_name_plural = "Payment Methods"

    def __str__(self):
        return f"{self.brand} ****{self.last_four}" if self.last_four else f"{self.type}"


class PaymentIntent(AbstractBaseModel):
    """Stripe payment intent tracking."""

    STATUS_CHOICES = [
        ("requires_payment_method", "Requires Payment Method"),
        ("requires_confirmation", "Requires Confirmation"),
        ("requires_action", "Requires Action"),
        ("processing", "Processing"),
        ("requires_capture", "Requires Capture"),
        ("canceled", "Canceled"),
        ("succeeded", "Succeeded"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_intents"
    )
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    client_secret = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Payment Intent"
        verbose_name_plural = "Payment Intents"

    def __str__(self):
        return f"Payment Intent {self.stripe_payment_intent_id} - ${self.amount}"


class Payment(AbstractBaseModel):
    """Payment record."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
        ("canceled", "Canceled"),
        ("refunded", "Refunded"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    payment_intent = models.OneToOneField(
        PaymentIntent,
        on_delete=models.CASCADE,
        related_name="payment",
        null=True,
        blank=True
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    stripe_charge_id = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.id} - ${self.amount} ({self.status})"
'''

    def _get_subscription_models_content(self) -> str:
        """Get the subscription models content."""
        return '''"""Subscription models."""

from django.db import models
from django.conf import settings
from core.models import AbstractBaseModel


class SubscriptionPlan(AbstractBaseModel):
    """Subscription plan."""

    INTERVAL_CHOICES = [
        ("day", "Daily"),
        ("week", "Weekly"),
        ("month", "Monthly"),
        ("year", "Yearly"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    stripe_price_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES)
    interval_count = models.PositiveIntegerField(default=1)
    trial_period_days = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    features = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"
        ordering = ["amount"]

    def __str__(self):
        return f"{self.name} - ${self.amount}/{self.interval}"


class Subscription(AbstractBaseModel):
    """User subscription."""

    STATUS_CHOICES = [
        ("incomplete", "Incomplete"),
        ("incomplete_expired", "Incomplete Expired"),
        ("trialing", "Trialing"),
        ("active", "Active"),
        ("past_due", "Past Due"),
        ("canceled", "Canceled"),
        ("unpaid", "Unpaid"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"

    @property
    def is_active(self):
        return self.status in ["active", "trialing"]
'''

    def _generate_schemas(self) -> None:
        """Generate payment schemas."""
        schemas_content = self._get_schemas_content()
        self.create_file(
            self.app_path / "schemas" / "payment_schema.py", schemas_content
        )

    def _get_schemas_content(self) -> str:
        """Get the payment schemas content."""
        base_schemas = '''"""Payment schemas."""

from core.schemas.base_schema import CamelCaseSchema
from typing import Optional
from decimal import Decimal


class PaymentMethodSchema(CamelCaseSchema):
    id: str
    type: str
    last_four: str
    brand: str
    is_default: bool
    created_at: str


class CreatePaymentMethodSchema(CamelCaseSchema):
    stripe_payment_method_id: str


class PaymentIntentSchema(CamelCaseSchema):
    id: str
    stripe_payment_intent_id: str
    amount: Decimal
    currency: str
    status: str
    client_secret: str
    created_at: str


class CreatePaymentIntentSchema(CamelCaseSchema):
    amount: Decimal
    currency: str = "usd"
    payment_method_id: Optional[str] = None
    description: Optional[str] = None


class PaymentSchema(CamelCaseSchema):
    id: str
    amount: Decimal
    currency: str
    status: str
    description: str
    created_at: str
    payment_method: Optional[PaymentMethodSchema] = None


class ProcessPaymentSchema(CamelCaseSchema):
    payment_intent_id: str
    payment_method_id: Optional[str] = None
'''

        if self.include_subscriptions:
            base_schemas += """

class SubscriptionPlanSchema(CamelCaseSchema):
    id: str
    name: str
    description: str
    amount: Decimal
    currency: str
    interval: str
    interval_count: int
    trial_period_days: Optional[int] = None
    features: list
    is_active: bool


class SubscriptionSchema(CamelCaseSchema):
    id: str
    plan: SubscriptionPlanSchema
    status: str
    current_period_start: str
    current_period_end: str
    trial_start: Optional[str] = None
    trial_end: Optional[str] = None
    canceled_at: Optional[str] = None


class CreateSubscriptionSchema(CamelCaseSchema):
    plan_id: str
    payment_method_id: Optional[str] = None
    trial_period_days: Optional[int] = None
"""

        return base_schemas

    def _generate_controllers(self) -> None:
        """Generate payment controllers."""
        from .templates.controller_templates import PAYMENTS_CONTROLLER_TEMPLATE

        controllers_content = PAYMENTS_CONTROLLER_TEMPLATE.format(
            app_name=self.app_name
        )
        self.create_file(
            self.app_path / "controllers" / "payment_controller.py", controllers_content
        )

    def _get_controllers_content(self) -> str:
        """Get the payment controllers content."""
        return f'''"""Payment controllers."""

import logging
from typing import List
from django.shortcuts import get_object_or_404
from ninja_extra import api_controller, http_delete, http_get, http_post, http_put

from {self.app_name}.models import Payment, PaymentMethod, PaymentIntent
from {self.app_name}.schemas.payment_schema import (
    PaymentSchema,
    PaymentMethodSchema,
    PaymentIntentSchema,
    CreatePaymentMethodSchema,
    CreatePaymentIntentSchema,
    ProcessPaymentSchema,
)
from {self.app_name}.services.stripe_service import StripeService

logger = logging.getLogger(__name__)


@api_controller("/payments", tags=["Payments"])
class PaymentController:
    """Payment management controller."""

    def __init__(self):
        self.stripe_service = StripeService()

    @http_get("/methods", response={{200: List[PaymentMethodSchema], 400: dict}})
    def list_payment_methods(self, request):
        """List user's payment methods."""
        try:
            methods = PaymentMethod.objects.filter(user=request.user)
            return 200, methods
        except Exception as e:
            logger.error(f"Error listing payment methods: {{e}}")
            return 400, {{"error": str(e)}}

    @http_post("/methods", response={{201: PaymentMethodSchema, 400: dict}})
    def create_payment_method(self, request, payload: CreatePaymentMethodSchema):
        """Create a new payment method."""
        try:
            payment_method = self.stripe_service.create_payment_method(
                request.user, payload.stripe_payment_method_id
            )
            return 201, payment_method
        except Exception as e:
            logger.error(f"Error creating payment method: {{e}}")
            return 400, {{"error": str(e)}}

    @http_delete("/methods/{{str:method_id}}", response={{204: dict, 400: dict}})
    def delete_payment_method(self, request, method_id: str):
        """Delete a payment method."""
        try:
            method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
            self.stripe_service.delete_payment_method(method)
            return 204, {{"message": "Payment method deleted successfully"}}
        except Exception as e:
            logger.error(f"Error deleting payment method: {{e}}")
            return 400, {{"error": str(e)}}

    @http_post("/intents", response={{201: PaymentIntentSchema, 400: dict}})
    def create_payment_intent(self, request, payload: CreatePaymentIntentSchema):
        """Create a payment intent."""
        try:
            intent = self.stripe_service.create_payment_intent(
                user=request.user,
                amount=payload.amount,
                currency=payload.currency,
                payment_method_id=payload.payment_method_id,
                description=payload.description,
            )
            return 201, intent
        except Exception as e:
            logger.error(f"Error creating payment intent: {{e}}")
            return 400, {{"error": str(e)}}

    @http_post("/process", response={{200: PaymentSchema, 400: dict}})
    def process_payment(self, request, payload: ProcessPaymentSchema):
        """Process a payment."""
        try:
            payment = self.stripe_service.process_payment(
                user=request.user,
                payment_intent_id=payload.payment_intent_id,
                payment_method_id=payload.payment_method_id,
            )
            return 200, payment
        except Exception as e:
            logger.error(f"Error processing payment: {{e}}")
            return 400, {{"error": str(e)}}

    @http_get("/", response={{200: List[PaymentSchema], 400: dict}})
    def list_payments(self, request):
        """List user's payments."""
        try:
            payments = Payment.objects.filter(user=request.user)
            return 200, payments
        except Exception as e:
            logger.error(f"Error listing payments: {{e}}")
            return 400, {{"error": str(e)}}

    @http_get("/{{str:payment_id}}", response={{200: PaymentSchema, 400: dict, 404: dict}})
    def get_payment(self, request, payment_id: str):
        """Get a specific payment."""
        try:
            payment = get_object_or_404(Payment, id=payment_id, user=request.user)
            return 200, payment
        except Exception as e:
            logger.error(f"Error getting payment: {{e}}")
            return 400, {{"error": str(e)}}
'''

    def _generate_services(self) -> None:
        """Generate payment services."""
        services_content = self._get_services_content()
        self.create_file(
            self.app_path / "services" / "__init__.py", "# Payment services"
        )
        self.create_file(
            self.app_path / "services" / "stripe_service.py", services_content
        )

    def _get_services_content(self) -> str:
        """Get the payment services content."""
        return f'''"""Stripe payment service."""

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from typing import Optional
from decimal import Decimal

from {self.app_name}.models import Payment, PaymentMethod, PaymentIntent

User = get_user_model()
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


class StripeService:
    """Service for handling Stripe operations."""

    def create_customer(self, user: User) -> str:
        """Create a Stripe customer for the user."""
        customer = stripe.Customer.create(
            email=user.email,
            name=f"{{user.first_name}} {{user.last_name}}".strip(),
            metadata={{"user_id": str(user.id)}}
        )
        return customer.id

    def get_or_create_customer(self, user: User) -> str:
        """Get or create a Stripe customer for the user."""
        # Check if user has a customer ID stored (you might want to add this field to User model)
        if hasattr(user, "stripe_customer_id") and user.stripe_customer_id:
            return user.stripe_customer_id

        # Create new customer
        customer_id = self.create_customer(user)

        # Store customer ID (implement this based on your User model)
        # user.stripe_customer_id = customer_id
        # user.save()

        return customer_id

    def create_payment_method(self, user: User, stripe_payment_method_id: str) -> PaymentMethod:
        """Create and attach a payment method to the user."""
        customer_id = self.get_or_create_customer(user)

        # Attach payment method to customer
        stripe.PaymentMethod.attach(
            stripe_payment_method_id,
            customer=customer_id,
        )

        # Get payment method details
        pm = stripe.PaymentMethod.retrieve(stripe_payment_method_id)

        # Create local payment method record
        payment_method = PaymentMethod.objects.create(
            user=user,
            stripe_payment_method_id=stripe_payment_method_id,
            type=pm.type,
            last_four=pm.card.last4 if pm.type == "card" else "",
            brand=pm.card.brand if pm.type == "card" else "",
        )

        # Set as default if it's the first payment method
        if not PaymentMethod.objects.filter(user=user, is_default=True).exists():
            payment_method.is_default = True
            payment_method.save()

        return payment_method

    def delete_payment_method(self, payment_method: PaymentMethod) -> None:
        """Delete a payment method."""
        # Detach from Stripe
        stripe.PaymentMethod.detach(payment_method.stripe_payment_method_id)

        # If this was the default, set another as default
        if payment_method.is_default:
            other_method = PaymentMethod.objects.filter(
                user=payment_method.user
            ).exclude(id=payment_method.id).first()
            if other_method:
                other_method.is_default = True
                other_method.save()

        # Delete local record
        payment_method.delete()

    def create_payment_intent(
        self,
        user: User,
        amount: Decimal,
        currency: str = "usd",
        payment_method_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> PaymentIntent:
        """Create a payment intent."""
        customer_id = self.get_or_create_customer(user)

        # Convert amount to cents
        amount_cents = int(amount * 100)

        intent_data = {{
            "amount": amount_cents,
            "currency": currency,
            "customer": customer_id,
            "automatic_payment_methods": {{"enabled": True}},
            "metadata": {{"user_id": str(user.id)}},
        }}

        if payment_method_id:
            intent_data["payment_method"] = payment_method_id

        if description:
            intent_data["description"] = description

        # Create Stripe payment intent
        stripe_intent = stripe.PaymentIntent.create(**intent_data)

        # Create local payment intent record
        payment_intent = PaymentIntent.objects.create(
            user=user,
            stripe_payment_intent_id=stripe_intent.id,
            amount=amount,
            currency=currency,
            status=stripe_intent.status,
            client_secret=stripe_intent.client_secret,
            metadata=stripe_intent.metadata,
        )

        return payment_intent

    def process_payment(
        self,
        user: User,
        payment_intent_id: str,
        payment_method_id: Optional[str] = None,
    ) -> Payment:
        """Process a payment using a payment intent."""
        # Get local payment intent
        payment_intent = PaymentIntent.objects.get(
            stripe_payment_intent_id=payment_intent_id,
            user=user
        )

        # Confirm the payment intent
        if payment_method_id:
            stripe.PaymentIntent.confirm(
                payment_intent_id,
                payment_method=payment_method_id,
            )
        else:
            stripe.PaymentIntent.confirm(payment_intent_id)

        # Get updated intent
        stripe_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        # Update local intent
        payment_intent.status = stripe_intent.status
        payment_intent.save()

        # Create payment record
        payment_method = None
        if payment_method_id:
            payment_method = PaymentMethod.objects.filter(
                stripe_payment_method_id=payment_method_id,
                user=user
            ).first()

        payment = Payment.objects.create(
            user=user,
            payment_intent=payment_intent,
            payment_method=payment_method,
            stripe_charge_id=stripe_intent.charges.data[0].id if stripe_intent.charges.data else "",
            amount=payment_intent.amount,
            currency=payment_intent.currency,
            status="succeeded" if stripe_intent.status == "succeeded" else "failed",
            metadata=stripe_intent.metadata,
        )

        return payment
'''

    def _generate_admin(self) -> None:
        """Generate payment admin."""
        admin_content = f'''"""Payment admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin
from {self.app_name}.models import Payment, PaymentMethod, PaymentIntent


@admin.register(PaymentMethod)
class PaymentMethodAdmin(ModelAdmin):
    list_display = ["id", "user", "type", "brand", "last_four", "is_default", "created_at"]
    list_filter = ["type", "brand", "is_default", "created_at"]
    search_fields = ["user__username", "user__email", "brand", "last_four"]
    readonly_fields = ["stripe_payment_method_id", "created_at", "updated_at"]


@admin.register(PaymentIntent)
class PaymentIntentAdmin(ModelAdmin):
    list_display = ["id", "user", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "currency", "created_at"]
    search_fields = ["user__username", "user__email", "stripe_payment_intent_id"]
    readonly_fields = ["stripe_payment_intent_id", "client_secret", "created_at", "updated_at"]


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ["id", "user", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "currency", "created_at"]
    search_fields = ["user__username", "user__email", "stripe_charge_id"]
    readonly_fields = ["stripe_charge_id", "created_at", "updated_at"]
'''
        self.create_file(self.app_path / "admin" / "payment_admin.py", admin_content)

    def _generate_tests(self) -> None:
        """Generate payment tests."""
        tests_content = f'''"""Payment tests."""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model

from {self.app_name}.models import Payment, PaymentMethod, PaymentIntent
from {self.app_name}.services.stripe_service import StripeService

User = get_user_model()


@pytest.fixture
def stripe_service():
    return StripeService()


@pytest.fixture
def payment_data():
    return {{
        "amount": Decimal("29.99"),
        "currency": "usd",
        "description": "Test payment",
    }}


@pytest.mark.django_db
class TestPaymentModels:
    def test_create_payment_method(self, test_user):
        payment_method = PaymentMethod.objects.create(
            user=test_user,
            stripe_payment_method_id="pm_test_123",
            type="card",
            last_four="4242",
            brand="visa",
        )
        assert str(payment_method) == "visa ****4242"

    def test_create_payment_intent(self, test_user):
        intent = PaymentIntent.objects.create(
            user=test_user,
            stripe_payment_intent_id="pi_test_123",
            amount=Decimal("29.99"),
            currency="usd",
            status="requires_confirmation",
            client_secret="pi_test_123_secret",
        )
        assert str(intent) == "Payment Intent pi_test_123 - $29.99"

    def test_create_payment(self, test_user):
        payment = Payment.objects.create(
            user=test_user,
            amount=Decimal("29.99"),
            currency="usd",
            status="succeeded",
        )
        assert str(payment) == f"Payment {{payment.id}} - $29.99 (succeeded)"


@pytest.mark.django_db
class TestStripeService:
    @patch("stripe.Customer.create")
    def test_create_customer(self, mock_create, stripe_service, test_user):
        mock_create.return_value = MagicMock(id="cus_test_123")

        customer_id = stripe_service.create_customer(test_user)

        assert customer_id == "cus_test_123"
        mock_create.assert_called_once()

    @patch("stripe.PaymentMethod.attach")
    @patch("stripe.PaymentMethod.retrieve")
    def test_create_payment_method(
        self, mock_retrieve, mock_attach, stripe_service, test_user
    ):
        mock_retrieve.return_value = MagicMock(
            type="card",
            card=MagicMock(last4="4242", brand="visa")
        )

        with patch.object(stripe_service, "get_or_create_customer", return_value="cus_test_123"):
            payment_method = stripe_service.create_payment_method(
                test_user, "pm_test_123"
            )

        assert payment_method.user == test_user
        assert payment_method.stripe_payment_method_id == "pm_test_123"
        assert payment_method.last_four == "4242"
        assert payment_method.brand == "visa"


@pytest.mark.django_db
class TestPaymentAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client
        return Client()

    def test_list_payment_methods(self, api_client, test_user, auth_headers):
        PaymentMethod.objects.create(
            user=test_user,
            stripe_payment_method_id="pm_test_123",
            type="card",
            last_four="4242",
            brand="visa",
        )

        response = api_client.get("/api/payments/methods", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["brand"] == "visa"
'''
        self.create_file(self.app_path / "tests" / "test_payment.py", tests_content)

    def _update_settings(self) -> None:
        """Update Django settings for payments."""
        settings_updates = {
            "STRIPE_PUBLISHABLE_KEY": "pk_test_...",
            "STRIPE_SECRET_KEY": "sk_test_...",
            "STRIPE_WEBHOOK_SECRET": "whsec_...",
        }
        self.update_settings(self.app_name, settings_updates)
