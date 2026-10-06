from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from core.schemas.base_schema import CamelCaseSchema

# Values match billing.models.Plan.INTERVAL_CHOICES.
PlanInterval = Literal["month", "year", "week", "day"]
# Values match billing.models.Subscription.STATUS_CHOICES.
SubscriptionStatus = Literal[
    "active", "canceled", "past_due", "trialing", "incomplete", "paused"
]
# Stripe redirects to these URLs, so only http(s) is useful.
REDIRECT_URL_PATTERN = r"^https?://\S+$"


class PlanSchema(CamelCaseSchema):
    id: str
    name: str
    description: str
    stripe_price_id: str
    stripe_product_id: str
    amount: Decimal
    currency: str
    interval: PlanInterval
    features: list[str]
    is_active: bool
    is_free: bool
    created_at: str
    updated_at: str

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class SubscriptionSchema(CamelCaseSchema):
    id: str
    user_id: str
    plan: PlanSchema
    stripe_subscription_id: str
    stripe_customer_id: str
    status: SubscriptionStatus
    current_period_start: str | None
    current_period_end: str | None
    cancel_at_period_end: bool
    canceled_at: str | None
    trial_start: str | None
    trial_end: str | None
    metadata: dict[str, Any]  # schema-ok: free-form Stripe metadata
    is_active: bool
    created_at: str
    updated_at: str

    @field_validator("id", "user_id", mode="before")
    @classmethod
    def convert_uuid(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    @field_validator(
        "created_at",
        "updated_at",
        "current_period_start",
        "current_period_end",
        "canceled_at",
        "trial_start",
        "trial_end",
        mode="before",
    )
    @classmethod
    def convert_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class CreateCheckoutSessionSchema(CamelCaseSchema):
    plan_id: str = Field(..., min_length=1)
    success_url: str = Field(..., pattern=REDIRECT_URL_PATTERN)
    cancel_url: str = Field(..., pattern=REDIRECT_URL_PATTERN)


class CheckoutSessionResponseSchema(CamelCaseSchema):
    session_id: str
    checkout_url: str


class CustomerPortalSchema(CamelCaseSchema):
    return_url: str = Field(..., pattern=REDIRECT_URL_PATTERN)


class CustomerPortalResponseSchema(CamelCaseSchema):
    portal_url: str
