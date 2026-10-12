"""Payments feature generator with Stripe integration."""

from .base_generator import BaseGenerator, GeneratorError
from .codegen import from_import, import_block, package_init

PAYMENT_MODELS = '''"""Payment models."""

from django.conf import settings
from django.db import models

from core.models import AbstractBaseModel


class StripeCustomer(AbstractBaseModel):
    """The Stripe customer that belongs to one user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stripe_customer",
    )
    stripe_customer_id = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Stripe Customer"
        verbose_name_plural = "Stripe Customers"

    def __str__(self):
        return self.stripe_customer_id


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
        related_name="payment_methods",
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
        return f"{self.brand} ****{self.last_four}" if self.last_four else self.type


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
        related_name="payment_intents",
    )
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    client_secret = models.TextField()

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
        related_name="payments",
    )
    payment_intent = models.OneToOneField(
        PaymentIntent,
        on_delete=models.CASCADE,
        related_name="payment",
        null=True,
        blank=True,
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    stripe_charge_id = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.id} - ${self.amount} ({self.status})"
'''

SUBSCRIPTION_MODELS = '''"""Subscription models."""

from django.conf import settings
from django.db import models

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
        related_name="payment_subscriptions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name="subscriptions",
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
        return f"{self.user} - {self.plan.name} ({self.status})"
'''

PAYMENT_SCHEMAS = '''"""Payment schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from core.schemas.base_schema import CamelCaseSchema


class PaymentMethodSchema(CamelCaseSchema):
    id: UUID
    type: str
    last_four: str
    brand: str
    is_default: bool
    created_at: datetime


class CreatePaymentMethodSchema(CamelCaseSchema):
    stripe_payment_method_id: str = Field(..., min_length=1, max_length=255)


class PaymentIntentSchema(CamelCaseSchema):
    id: UUID
    stripe_payment_intent_id: str
    amount: Decimal
    currency: str
    status: str
    client_secret: str
    created_at: datetime


class CreatePaymentIntentSchema(CamelCaseSchema):
    amount: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    currency: str = Field("usd", min_length=3, max_length=3)
    payment_method_id: UUID | None = None
    description: str = Field("", max_length=1000)


class PaymentSchema(CamelCaseSchema):
    id: UUID
    amount: Decimal
    currency: str
    status: str
    description: str
    created_at: datetime
    payment_method: PaymentMethodSchema | None = None


class ProcessPaymentSchema(CamelCaseSchema):
    payment_intent_id: UUID
    payment_method_id: UUID | None = None
'''

PAYMENT_SCHEMA_NAMES = (
    "CreatePaymentIntentSchema",
    "CreatePaymentMethodSchema",
    "PaymentIntentSchema",
    "PaymentMethodSchema",
    "PaymentSchema",
    "ProcessPaymentSchema",
)

# Every query filters on the owner, so another user's record is a 404. Stripe
# calls stay here; the controller never touches the ORM or the SDK.
PAYMENT_SERVICE = '''"""Payment service. Every query is scoped to the owner. Stripe calls live here."""

from typing import Any
from uuid import UUID

import stripe
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

{first_party_imports}

# Stripe intent statuses that map to a Payment status. Any other status
# (requires_action, requires_confirmation, ...) leaves the payment pending.
PAYMENT_STATUSES = {{
    "succeeded": "succeeded",
    "processing": "processing",
    "canceled": "canceled",
}}


class PaymentService:
    """Owner-scoped payments backed by Stripe."""

    def _api_key(self) -> str:
        """Return the Stripe secret key. Fail loud when it is not set."""
        api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
        if not api_key:
            msg = "STRIPE_SECRET_KEY is not set"
            raise ImproperlyConfigured(msg)
        return api_key

    def list_payments(self, user: Any) -> QuerySet[Payment]:
        """Return the user's payments, newest first."""
        return (
            Payment.objects.filter(user=user)
            .select_related("payment_method")
            .order_by("-created_at")
        )

    def get_payment(self, payment_id: UUID, user: Any) -> Payment:
        """Return one payment owned by the user. Raise Http404 for any other."""
        return get_object_or_404(
            Payment.objects.select_related("payment_method"), id=payment_id, user=user
        )

    def list_payment_methods(self, user: Any) -> QuerySet[PaymentMethod]:
        """Return the user's payment methods, default first."""
        return PaymentMethod.objects.filter(user=user).order_by(
            "-is_default", "-created_at"
        )

    def get_payment_method(self, method_id: UUID, user: Any) -> PaymentMethod:
        """Return one payment method owned by the user. Raise Http404 for any other."""
        return get_object_or_404(PaymentMethod, id=method_id, user=user)

    def get_or_create_customer_id(self, user: Any) -> str:
        """Return the user's Stripe customer ID. Create the customer once."""
        customer = StripeCustomer.objects.filter(user=user).first()
        if customer is not None:
            return customer.stripe_customer_id
        stripe_customer = stripe.Customer.create(
            api_key=self._api_key(),
            email=user.email,
            name=f"{{user.first_name}} {{user.last_name}}".strip(),
            metadata={{"user_id": str(user.id)}},
        )
        StripeCustomer.objects.create(user=user, stripe_customer_id=stripe_customer.id)
        return stripe_customer.id

    def create_payment_method(
        self, user: Any, payload: CreatePaymentMethodSchema
    ) -> PaymentMethod:
        """Attach a Stripe payment method to the user and store it."""
        api_key = self._api_key()
        stripe_id = payload.stripe_payment_method_id
        stripe.PaymentMethod.attach(
            stripe_id, customer=self.get_or_create_customer_id(user), api_key=api_key
        )
        stripe_method = stripe.PaymentMethod.retrieve(stripe_id, api_key=api_key)
        card = stripe_method.card if stripe_method.type == "card" else None
        has_default = PaymentMethod.objects.filter(user=user, is_default=True).exists()
        return PaymentMethod.objects.create(
            user=user,
            stripe_payment_method_id=stripe_id,
            type=stripe_method.type,
            last_four=card.last4 if card else "",
            brand=card.brand if card else "",
            is_default=not has_default,
        )

    def delete_payment_method(self, method_id: UUID, user: Any) -> None:
        """Detach a payment method owned by the user and delete it."""
        method = self.get_payment_method(method_id, user)
        stripe.PaymentMethod.detach(
            method.stripe_payment_method_id, api_key=self._api_key()
        )
        if method.is_default:
            replacement = (
                PaymentMethod.objects.filter(user=user).exclude(id=method.id).first()
            )
            if replacement is not None:
                replacement.is_default = True
                replacement.save(update_fields=["is_default", "updated_at"])
        method.delete()

    def create_payment_intent(
        self, user: Any, payload: CreatePaymentIntentSchema
    ) -> PaymentIntent:
        """Create a Stripe payment intent for the user and store it."""
        params: dict[str, Any] = {{
            "amount": int(payload.amount * 100),
            "currency": payload.currency,
            "automatic_payment_methods": {{"enabled": True}},
            "metadata": {{"user_id": str(user.id)}},
        }}
        if payload.payment_method_id is not None:
            method = self.get_payment_method(payload.payment_method_id, user)
            params["payment_method"] = method.stripe_payment_method_id
        if payload.description:
            params["description"] = payload.description
        params["customer"] = self.get_or_create_customer_id(user)
        stripe_intent = stripe.PaymentIntent.create(api_key=self._api_key(), **params)
        return PaymentIntent.objects.create(
            user=user,
            stripe_payment_intent_id=stripe_intent.id,
            amount=payload.amount,
            currency=payload.currency,
            status=stripe_intent.status,
            client_secret=stripe_intent.client_secret,
        )

    def process_payment(self, user: Any, payload: ProcessPaymentSchema) -> Payment:
        """Confirm a payment intent owned by the user and record the payment."""
        intent = get_object_or_404(
            PaymentIntent, id=payload.payment_intent_id, user=user
        )
        if Payment.objects.filter(payment_intent=intent).exists():
            msg = "This payment intent is already processed"
            raise ConflictError(msg)
        method = None
        confirm_params: dict[str, Any] = {{}}
        if payload.payment_method_id is not None:
            method = self.get_payment_method(payload.payment_method_id, user)
            confirm_params["payment_method"] = method.stripe_payment_method_id
        stripe_intent = stripe.PaymentIntent.confirm(
            intent.stripe_payment_intent_id, api_key=self._api_key(), **confirm_params
        )
        intent.status = stripe_intent.status
        intent.save(update_fields=["status", "updated_at"])
        return Payment.objects.create(
            user=user,
            payment_intent=intent,
            payment_method=method,
            stripe_charge_id=stripe_intent.latest_charge or "",
            amount=intent.amount,
            currency=intent.currency,
            status=PAYMENT_STATUSES.get(stripe_intent.status, "pending"),
            description=stripe_intent.description or "",
        )
'''

PAYMENT_ADMIN = '''"""Payment admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin

{first_party_imports}


@admin.register(PaymentMethod)
class PaymentMethodAdmin(ModelAdmin):
    list_display = [
        "id",
        "user",
        "type",
        "brand",
        "last_four",
        "is_default",
        "created_at",
    ]
    list_filter = ["type", "brand", "is_default", "created_at"]
    search_fields = ["user__username", "user__email", "brand", "last_four"]
    readonly_fields = ["stripe_payment_method_id", "created_at", "updated_at"]


@admin.register(PaymentIntent)
class PaymentIntentAdmin(ModelAdmin):
    list_display = ["id", "user", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "currency", "created_at"]
    search_fields = ["user__username", "user__email", "stripe_payment_intent_id"]
    readonly_fields = [
        "stripe_payment_intent_id",
        "client_secret",
        "created_at",
        "updated_at",
    ]


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ["id", "user", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "currency", "created_at"]
    search_fields = ["user__username", "user__email", "stripe_charge_id"]
    readonly_fields = ["stripe_charge_id", "created_at", "updated_at"]
'''

SUBSCRIPTION_ADMIN = '''"""Subscription admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin

{first_party_imports}


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(ModelAdmin):
    list_display = ["name", "amount", "currency", "interval", "is_active"]
    list_filter = ["interval", "currency", "is_active"]
    search_fields = ["name", "stripe_price_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ["id", "user", "plan", "status", "current_period_end"]
    list_filter = ["status", "plan"]
    search_fields = ["user__username", "user__email", "stripe_subscription_id"]
    readonly_fields = ["stripe_subscription_id", "created_at", "updated_at"]
'''

# Smoke, permission and contract tests only. No test reaches Stripe: the
# Stripe routes are covered at their auth and ownership boundary, which fails
# before the service calls the SDK.
PAYMENT_TESTS = '''"""Smoke and permission tests for the {app_name} API. No test calls Stripe."""

import pytest

{first_party_imports}


def _payment_method(user, stripe_id):
    return PaymentMethod.objects.create(
        user=user,
        stripe_payment_method_id=stripe_id,
        type="card",
        last_four="4242",
        brand="visa",
    )


@pytest.mark.django_db
class TestPaymentAPI:
    """Owner scoping, validation and the auth boundary of the Stripe routes."""

    @pytest.fixture(autouse=True)
    def _no_stripe_key(self, settings):
        # A route that reaches Stripe fails with ImproperlyConfigured instead
        # of making a network call.
        settings.STRIPE_SECRET_KEY = ""

    def test_list_methods_as_owner_returns_only_own(self, authenticated_client):
        client, user = authenticated_client
        mine = _payment_method(user, "pm_mine")
        _payment_method(UserFactory(), "pm_theirs")
        response = client.get("/api/payments/methods")
        assert response.status_code == 200
        assert [method["id"] for method in response.json()] == [str(mine.id)]

    def test_other_user_cannot_read_payment(self, authenticated_client):
        client, _ = authenticated_client
        payment = Payment.objects.create(user=UserFactory(), amount="10.00")
        response = client.get(f"/api/payments/{{payment.id}}")
        assert response.status_code == 404

    def test_other_user_cannot_delete_payment_method(self, authenticated_client):
        client, _ = authenticated_client
        method = _payment_method(UserFactory(), "pm_theirs")
        response = client.delete(f"/api/payments/methods/{{method.id}}")
        assert response.status_code == 404
        assert PaymentMethod.objects.filter(id=method.id).exists()

    def test_create_intent_with_invalid_amount_returns_422(self, authenticated_client):
        client, _ = authenticated_client
        response = client.post(
            "/api/payments/intents", {{"amount": "-1"}}, content_type="application/json"
        )
        assert_validation_error(response, field="amount")

    @pytest.mark.parametrize(
        "path",
        ["/api/payments/methods", "/api/payments/intents", "/api/payments/process"],
    )
    def test_stripe_routes_require_auth(self, api_client, path):
        response = api_client.post(path, {{}}, content_type="application/json")
        assert response.status_code == 401
'''


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
        if self.app_path.exists():
            msg = f"App '{self.app_name}' already exists"
            raise GeneratorError(msg)

        print(
            f"Generating payments feature with {self.provider} for {self.platform_type} platform..."
        )
        self.create_django_app()
        self.remove_scaffold()
        self.update_pyproject_toml(["stripe>=15.1.0"])
        self._generate_models()
        self._generate_schemas()
        self._generate_services()
        self._generate_controllers()
        self._generate_admin()
        self._generate_tests()
        self.update_settings(self.app_name, {})
        self.update_urls(self.app_name, "PaymentController")
        self.create_migration()
        print("Payments feature generated successfully!")

    def _app_import(self, module: str, *names: str) -> str:
        """Return ``from <app>.<module> import names`` for this app."""
        return from_import(f"{self.app_name}.{module}", *names)

    def _generate_models(self) -> None:
        """Generate payment models."""
        models_path = self.app_path / "models"
        self.create_file(models_path / "payment.py", PAYMENT_MODELS)
        exports = [
            (
                f"{self.app_name}.models.payment",
                ["Payment", "PaymentIntent", "PaymentMethod", "StripeCustomer"],
            )
        ]
        if self.include_subscriptions:
            self.create_file(models_path / "subscription.py", SUBSCRIPTION_MODELS)
            exports.append(
                (
                    f"{self.app_name}.models.subscription",
                    ["Subscription", "SubscriptionPlan"],
                )
            )
        self.create_file(models_path / "__init__.py", package_init(*exports))

    def _generate_schemas(self) -> None:
        """Generate payment schemas."""
        schemas_path = self.app_path / "schemas"
        self.create_file(schemas_path / "payment_schema.py", PAYMENT_SCHEMAS)
        self.create_file(
            schemas_path / "__init__.py",
            package_init(
                (f"{self.app_name}.schemas.payment_schema", list(PAYMENT_SCHEMA_NAMES))
            ),
        )

    def _generate_services(self) -> None:
        """Generate the owner-scoped payment service."""
        services_path = self.app_path / "services"
        first_party_imports = import_block(
            "from api.exceptions import ConflictError",
            self._app_import(
                "models", "Payment", "PaymentIntent", "PaymentMethod", "StripeCustomer"
            ),
            self._app_import(
                "schemas",
                "CreatePaymentIntentSchema",
                "CreatePaymentMethodSchema",
                "ProcessPaymentSchema",
            ),
        )
        self.create_file(
            services_path / "payment_service.py",
            PAYMENT_SERVICE.format(first_party_imports=first_party_imports),
        )
        self.create_file(
            services_path / "__init__.py",
            package_init(
                (f"{self.app_name}.services.payment_service", ["PaymentService"])
            ),
        )

    def _generate_controllers(self) -> None:
        """Generate the payment controller."""
        from .templates.payments_templates import render_payments_controller

        controllers_path = self.app_path / "controllers"
        self.create_file(
            controllers_path / "payment_controller.py",
            render_payments_controller(self.app_name),
        )
        self.create_file(
            controllers_path / "__init__.py",
            package_init(
                (
                    f"{self.app_name}.controllers.payment_controller",
                    ["PaymentController"],
                )
            ),
        )

    def _generate_admin(self) -> None:
        """Generate payment admin."""
        admin_path = self.app_path / "admin"
        self.create_file(
            admin_path / "payment_admin.py",
            PAYMENT_ADMIN.format(
                first_party_imports=self._app_import(
                    "models", "Payment", "PaymentIntent", "PaymentMethod"
                )
            ),
        )
        exports = [
            (
                f"{self.app_name}.admin.payment_admin",
                ["PaymentAdmin", "PaymentIntentAdmin", "PaymentMethodAdmin"],
            )
        ]
        if self.include_subscriptions:
            self.create_file(
                admin_path / "subscription_admin.py",
                SUBSCRIPTION_ADMIN.format(
                    first_party_imports=self._app_import(
                        "models", "Subscription", "SubscriptionPlan"
                    )
                ),
            )
            exports.append(
                (
                    f"{self.app_name}.admin.subscription_admin",
                    ["SubscriptionAdmin", "SubscriptionPlanAdmin"],
                )
            )
        self.create_file(admin_path / "__init__.py", package_init(*exports))

    def _generate_tests(self) -> None:
        """Generate the payment smoke and permission tests."""
        first_party_imports = import_block(
            "from core.tests.factories import UserFactory",
            self._app_import("models", "Payment", "PaymentMethod"),
            "from tests.utils.assertions import assert_validation_error",
        )
        self.create_file(
            self.app_path / "tests" / "test_payment.py",
            PAYMENT_TESTS.format(
                app_name=self.app_name, first_party_imports=first_party_imports
            ),
        )
