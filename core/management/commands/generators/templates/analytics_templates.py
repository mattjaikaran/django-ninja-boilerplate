"""Analytics generator templates.

The app stores product events in the database: a user tracks and lists their
own events, and staff read event totals. It adds no settings and no
dependencies. Every template is verbatim code: ``fill_imports`` puts the app's
isort block where ``{first_party_imports}`` stands.
"""

from core.management.commands.generators.codegen import (
    fill_imports,
    from_import,
    package_init,
)

EVENT_MODEL_TEMPLATE = '''"""Analytics event model."""

from django.conf import settings
from django.db import models

{first_party_imports}


class Event(TimestampedModel):
    """One product event a user triggered, for example ``report.exported``."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_events",
    )
    name = models.CharField(max_length=100)
    properties = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Analytics Event"
        verbose_name_plural = "Analytics Events"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["name", "created_at"]),
        ]

    def __str__(self):
        return self.name
'''

ANALYTICS_SCHEMAS_TEMPLATE = '''"""Analytics schemas."""

from datetime import datetime
from typing import Annotated

from pydantic import BeforeValidator, Field

{first_party_imports}

# Serialize the UUID primary key as a string.
UUIDStr = Annotated[str, BeforeValidator(str)]
# Lowercase dotted names such as "report.exported" keep the totals groupable.
EventName = Annotated[
    str, Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_.:-]+$")
]
PropertyValue = str | int | float | bool | None


class EventSchema(CamelCaseSchema):
    id: UUIDStr
    name: str
    properties: dict[str, PropertyValue]
    created_at: datetime


class TrackEventSchema(CamelCaseSchema):
    name: EventName
    properties: dict[str, PropertyValue] = Field(default_factory=dict, max_length=50)


class EventFilterSchema(CamelCaseSchema):
    name: str | None = Field(None, max_length=100)


class SummaryFilterSchema(CamelCaseSchema):
    days: int = Field(30, ge=1, le=365)


class EventCountSchema(CamelCaseSchema):
    name: str
    count: int
'''

ANALYTICS_SERVICE_TEMPLATE = '''"""Analytics events. Users track and read their own; staff read totals."""

from datetime import timedelta
from typing import Any

from django.db.models import Count, QuerySet
from django.utils import timezone

{first_party_imports}

# The newest events a user can list in one request.
LIST_LIMIT = 100


class AnalyticsService:
    """Owner-scoped event tracking and a cross-user summary for staff."""

    def track(self, user: Any, payload: TrackEventSchema) -> Event:
        """Record one event for the user."""
        return Event.objects.create(user=user, **payload.model_dump())

    def list_for_user(self, user: Any, name: str | None = None) -> QuerySet[Event]:
        """Return the user's newest events, optionally for one event name."""
        events = Event.objects.filter(user=user)
        if name:
            events = events.filter(name=name)
        return events.order_by("-created_at")[:LIST_LIMIT]

    def summary(self, days: int) -> list[dict[str, Any]]:
        """Count every user's events per name over the last ``days`` days.

        The result is not scoped to one user: only staff routes call it.
        """
        since = timezone.now() - timedelta(days=days)
        return list(
            Event.objects.filter(created_at__gte=since)
            .values("name")
            .annotate(count=Count("id"))
            .order_by("-count", "name")
        )
'''

# JWTAuth on the controller, IsAdminUser on the cross-user summary.
ANALYTICS_CONTROLLER_TEMPLATE = '''"""Analytics controller. Users track their own events; staff read totals."""

from ninja import Query
from ninja_extra import api_controller, http_get, http_post
from ninja_jwt.authentication import JWTAuth

{first_party_imports}


@api_controller("/analytics", tags=["Analytics"], auth=JWTAuth())
class AnalyticsController:
    """Event tracking for the authenticated user and a staff-only summary."""

    def __init__(self):
        self.service = AnalyticsService()

    @http_get("/events", response={200: list[EventSchema]})
    @log_api_call()
    def list_events(self, request, filters: Query[EventFilterSchema]):
        """List the user's newest events, optionally for one event name."""
        return 200, self.service.list_for_user(request.user, filters.name)

    @http_post("/events", response={201: EventSchema})
    @log_api_call(include_payload=True)
    def track_event(self, request, payload: TrackEventSchema):
        """Record one event for the user."""
        return 201, self.service.track(request.user, payload)

    @http_get(
        "/summary",
        response={200: list[EventCountSchema], 403: dict},
        permissions=[IsAdminUser],
    )
    @log_api_call()
    def get_summary(self, request, filters: Query[SummaryFilterSchema]):
        """Count every user's events per name. Staff only."""
        return 200, self.service.summary(filters.days)
'''

ANALYTICS_TESTS_TEMPLATE = '''"""Smoke, ownership and permission tests for the analytics API."""

import pytest
from ninja_jwt.tokens import RefreshToken

{first_party_imports}


@pytest.fixture
def staff_client(api_client, staff_user):
    token = RefreshToken.for_user(staff_user).access_token
    api_client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return api_client


@pytest.mark.django_db
class TestAnalyticsAPI:
    """Users track and list their own events; only staff read the summary."""

    def test_anonymous_cannot_track(self, api_client):
        response = api_client.post(
            "/api/analytics/events", {"name": "signup"}, content_type="application/json"
        )
        assert response.status_code == 401

    def test_user_tracks_own_event(self, authenticated_client):
        client, user = authenticated_client
        response = client.post(
            "/api/analytics/events",
            {"name": "report.exported", "properties": {"format": "csv"}},
            content_type="application/json",
        )
        assert response.status_code == 201
        assert Event.objects.get(user=user).properties == {"format": "csv"}

    def test_invalid_event_name_returns_422(self, authenticated_client):
        client, _ = authenticated_client
        response = client.post(
            "/api/analytics/events",
            {"name": "Report Exported"},
            content_type="application/json",
        )
        assert_validation_error(response, field="name")

    def test_list_returns_only_own_events(self, authenticated_client):
        client, user = authenticated_client
        Event.objects.create(user=user, name="mine")
        Event.objects.create(user=UserFactory(), name="theirs")
        response = client.get("/api/analytics/events")
        assert response.status_code == 200
        assert [event["name"] for event in response.json()] == ["mine"]

    def test_regular_user_cannot_read_summary(self, authenticated_client):
        client, _ = authenticated_client
        response = client.get("/api/analytics/summary")
        assert response.status_code == 403

    def test_staff_reads_summary_across_users(self, staff_client):
        for name in ("signup", "signup", "login"):
            Event.objects.create(user=UserFactory(), name=name)
        response = staff_client.get("/api/analytics/summary?days=7")
        assert response.status_code == 200
        assert response.json() == [
            {"name": "signup", "count": 2},
            {"name": "login", "count": 1},
        ]
'''


def render_analytics_files(app_name: str) -> dict[str, str]:
    """Return the generated files keyed by path relative to the app directory."""
    schemas = [
        "EventCountSchema",
        "EventFilterSchema",
        "EventSchema",
        "SummaryFilterSchema",
        "TrackEventSchema",
    ]
    return {
        "models/event.py": fill_imports(
            EVENT_MODEL_TEMPLATE, from_import("core.models", "TimestampedModel")
        ),
        "schemas/analytics_schema.py": fill_imports(
            ANALYTICS_SCHEMAS_TEMPLATE,
            from_import("core.schemas.base_schema", "CamelCaseSchema"),
        ),
        "services/analytics_service.py": fill_imports(
            ANALYTICS_SERVICE_TEMPLATE,
            from_import(f"{app_name}.models", "Event"),
            from_import(f"{app_name}.schemas", "TrackEventSchema"),
        ),
        "controllers/analytics_controller.py": fill_imports(
            ANALYTICS_CONTROLLER_TEMPLATE,
            from_import("api.decorators", "log_api_call"),
            from_import("api.permissions", "IsAdminUser"),
            from_import(
                f"{app_name}.schemas",
                "EventCountSchema",
                "EventFilterSchema",
                "EventSchema",
                "SummaryFilterSchema",
                "TrackEventSchema",
            ),
            from_import(f"{app_name}.services", "AnalyticsService"),
        ),
        "tests/test_analytics.py": fill_imports(
            ANALYTICS_TESTS_TEMPLATE,
            from_import("core.tests.factories", "UserFactory"),
            from_import(f"{app_name}.models", "Event"),
            from_import("tests.utils.assertions", "assert_validation_error"),
        ),
        "models/__init__.py": package_init((f"{app_name}.models.event", ["Event"])),
        "schemas/__init__.py": package_init(
            (f"{app_name}.schemas.analytics_schema", schemas)
        ),
        "services/__init__.py": package_init(
            (f"{app_name}.services.analytics_service", ["AnalyticsService"])
        ),
        "controllers/__init__.py": package_init(
            (f"{app_name}.controllers.analytics_controller", ["AnalyticsController"])
        ),
    }
