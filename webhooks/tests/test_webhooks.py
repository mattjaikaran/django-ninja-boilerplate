import pytest
from django.contrib.auth import get_user_model
from ninja_jwt.tokens import RefreshToken

from core.tests.factories import UserFactory
from webhooks.models import Webhook, WebhookDelivery
from webhooks.utils import dispatch_webhook

User = get_user_model()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def auth_headers(user):
    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.fixture
def webhook(user):
    return Webhook.objects.create(
        name="Test Webhook",
        url="https://example.com/hook",
        events=["user.created"],
        created_by=user,
    )


@pytest.mark.django_db
class TestWebhookModel:
    def test_create_webhook(self, user):
        webhook = Webhook.objects.create(
            name="My Hook",
            url="https://example.com/hook",
            events=["order.paid"],
            created_by=user,
        )
        assert webhook.id is not None
        assert webhook.is_active is True
        assert "order.paid" in webhook.events

    def test_webhook_str(self, webhook):
        assert webhook.name in str(webhook)
        assert webhook.url in str(webhook)

    def test_webhook_delivery_is_successful(self, webhook):
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event="user.created",
            payload={"user_id": "123"},
            response_status=200,
        )
        assert delivery.is_successful is True

    def test_webhook_delivery_not_successful_on_5xx(self, webhook):
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event="user.created",
            payload={"user_id": "123"},
            response_status=500,
        )
        assert delivery.is_successful is False

    def test_webhook_delivery_not_successful_when_none(self, webhook):
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event="user.created",
            payload={"user_id": "123"},
        )
        assert delivery.is_successful is False


@pytest.mark.django_db
class TestWebhookAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client

        return Client()

    def test_create_webhook(self, api_client, auth_headers, user):
        data = {
            "name": "New Hook",
            "url": "https://example.com/hook",
            "events": ["user.created"],
        }
        response = api_client.post(
            "/api/webhooks/",
            data,
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 201
        assert Webhook.objects.filter(created_by=user).exists()

    def test_list_webhooks(self, api_client, auth_headers, user, webhook):
        response = api_client.get("/api/webhooks/", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(w["name"] == webhook.name for w in data)

    def test_get_webhook(self, api_client, auth_headers, webhook):
        response = api_client.get(f"/api/webhooks/{webhook.id}", **auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == webhook.name

    def test_update_webhook(self, api_client, auth_headers, webhook):
        response = api_client.put(
            f"/api/webhooks/{webhook.id}",
            {"name": "Updated Hook"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        webhook.refresh_from_db()
        assert webhook.name == "Updated Hook"

    def test_delete_webhook(self, api_client, auth_headers, webhook):
        response = api_client.delete(f"/api/webhooks/{webhook.id}", **auth_headers)
        assert response.status_code == 204
        assert not Webhook.objects.filter(id=webhook.id).exists()

    def test_list_deliveries(self, api_client, auth_headers, webhook):
        WebhookDelivery.objects.create(
            webhook=webhook,
            event="user.created",
            payload={"user_id": "abc"},
        )
        response = api_client.get(
            f"/api/webhooks/{webhook.id}/deliveries", **auth_headers
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_cannot_access_other_users_webhook(self, api_client, auth_headers):
        other_user = UserFactory()
        other_webhook = Webhook.objects.create(
            name="Other Hook",
            url="https://example.com/other",
            events=["order.paid"],
            created_by=other_user,
        )
        response = api_client.get(f"/api/webhooks/{other_webhook.id}", **auth_headers)
        assert response.status_code == 404


@pytest.mark.django_db
class TestDispatchWebhook:
    def test_dispatch_creates_delivery(self, user):
        Webhook.objects.create(
            name="Listener",
            url="https://example.com/hook",
            events=["user.created"],
            is_active=True,
            created_by=user,
        )
        # Prevent actual Celery task execution
        from unittest.mock import patch

        with patch("webhooks.tasks.deliver_webhook") as mock_task:
            mock_task.delay = lambda *_a, **_kw: None
            dispatch_webhook("user.created", {"user_id": "xyz"})

        assert WebhookDelivery.objects.filter(event="user.created").exists()

    def test_dispatch_does_not_create_delivery_for_unmatched_event(self, user):
        Webhook.objects.create(
            name="Listener",
            url="https://example.com/hook",
            events=["order.paid"],
            is_active=True,
            created_by=user,
        )
        from unittest.mock import patch

        with patch("webhooks.tasks.deliver_webhook") as mock_task:
            mock_task.delay = lambda *_a, **_kw: None
            dispatch_webhook("user.created", {"user_id": "xyz"})

        assert not WebhookDelivery.objects.filter(event="user.created").exists()

    def test_dispatch_skips_inactive_webhooks(self, user):
        Webhook.objects.create(
            name="Inactive Listener",
            url="https://example.com/hook",
            events=["user.created"],
            is_active=False,
            created_by=user,
        )
        from unittest.mock import patch

        with patch("webhooks.tasks.deliver_webhook") as mock_task:
            mock_task.delay = lambda *_a, **_kw: None
            dispatch_webhook("user.created", {"user_id": "xyz"})

        assert not WebhookDelivery.objects.filter(event="user.created").exists()
