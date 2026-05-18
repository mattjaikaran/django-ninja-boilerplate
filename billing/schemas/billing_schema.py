from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ninja import Schema
from pydantic import field_validator


class PlanSchema(Schema):
    id: str
    name: str
    description: str
    stripe_price_id: str
    stripe_product_id: str
    amount: Decimal
    currency: str
    interval: str
    features: list
    is_active: bool
    is_free: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

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


class SubscriptionSchema(Schema):
    id: str
    user_id: str
    plan: PlanSchema
    stripe_subscription_id: str
    stripe_customer_id: str
    status: str
    current_period_start: str | None
    current_period_end: str | None
    cancel_at_period_end: bool
    canceled_at: str | None
    trial_start: str | None
    trial_end: str | None
    metadata: dict
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

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


class CreateCheckoutSessionSchema(Schema):
    plan_id: str
    success_url: str
    cancel_url: str


class CheckoutSessionResponseSchema(Schema):
    session_id: str
    checkout_url: str


class CustomerPortalSchema(Schema):
    return_url: str


class CustomerPortalResponseSchema(Schema):
    portal_url: str
