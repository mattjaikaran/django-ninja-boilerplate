import socket

import httpx
import pytest
from django.contrib.auth import get_user_model
from ninja_jwt.tokens import RefreshToken

from core.tests.factories import UserFactory
from webhooks.models import Webhook, WebhookDelivery
from webhooks.ssrf import UnsafeWebhookURLError, post_webhook, validate_webhook_url
from webhooks.tasks import deliver_webhook
from webhooks.utils import dispatch_webhook

User = get_user_model()

PUBLIC_IP = "93.184.215.14"


def _resolve_to(*ips: str):
    """Return a getaddrinfo stand-in that resolves every host to ``ips``."""

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET6 if ":" in ip else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (ip, port),
            )
            for ip in ips
        ]

    return fake_getaddrinfo


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _resolve_to(PUBLIC_IP))


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def auth_headers(user):
    refresh = RefreshToken.for_user(user)
    return {"HTTP_COOKIE": f"access_token={refresh.access_token}"}


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
@pytest.mark.usefixtures("public_dns")
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


class _Chunks(httpx.SyncByteStream):
    """Unread response body, like a real network stream."""

    def __init__(self, *chunks: bytes) -> None:
        self._chunks = chunks

    def __iter__(self):
        yield from self._chunks


class TestWebhookSSRF:
    @pytest.mark.parametrize(
        "url",
        [
            "https://127.0.0.1/hook",
            "https://10.1.2.3/hook",
            "https://169.254.169.254/latest/meta-data/",
            "https://[::1]/hook",
            "https://[::ffff:169.254.169.254]/hook",
            "https://2130706433/hook",  # 127.0.0.1 as a decimal integer
        ],
    )
    def test_rejects_non_public_address(self, url):
        with pytest.raises(UnsafeWebhookURLError):
            validate_webhook_url(url)

    def test_rejects_hostname_resolving_to_private_ip(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _resolve_to("10.0.0.7"))
        with pytest.raises(UnsafeWebhookURLError):
            validate_webhook_url("https://internal.example.com/hook")

    def test_rejects_when_any_resolved_ip_is_private(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", _resolve_to(PUBLIC_IP, "::1"))
        with pytest.raises(UnsafeWebhookURLError):
            validate_webhook_url("https://mixed.example.com/hook")

    @pytest.mark.parametrize(
        "url", ["http://example.com/hook", "ftp://example.com/hook", "file:///etc"]
    )
    def test_rejects_non_https_scheme(self, url, settings, public_dns):
        settings.DEBUG = False
        settings.WEBHOOKS_ALLOW_HTTP = False
        with pytest.raises(UnsafeWebhookURLError):
            validate_webhook_url(url)

    def test_accepts_public_https_host(self, public_dns):
        vetted = validate_webhook_url("https://example.com/hook")
        assert str(vetted.ip) == PUBLIC_IP

    def test_pins_vetted_ip_and_does_not_follow_redirects(self, public_dns):
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(
                302,
                headers={"Location": "http://169.254.169.254/latest/"},
                stream=_Chunks(b""),
            )

        response = post_webhook(
            "https://example.com/hook",
            b"{}",
            {"Host": "169.254.169.254"},
            transport=httpx.MockTransport(handler),
        )

        assert response.status_code == 302
        assert len(seen) == 1
        assert seen[0].url.host == PUBLIC_IP
        assert seen[0].headers["Host"] == "example.com"
        assert seen[0].extensions["sni_hostname"] == "example.com"

    def test_caps_stored_response_body(self, public_dns):
        from webhooks.ssrf import MAX_RESPONSE_BYTES

        chunk = b"x" * MAX_RESPONSE_BYTES
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(200, stream=_Chunks(chunk, chunk, chunk))
        )
        response = post_webhook(
            "https://example.com/hook", b"{}", {}, transport=transport
        )
        assert len(response.body) == MAX_RESPONSE_BYTES

    @pytest.mark.django_db
    def test_delivery_to_blocked_url_records_error_without_retry(self, user):
        webhook = Webhook.objects.create(
            name="Metadata",
            url="https://169.254.169.254/latest/meta-data/",
            events=["user.created"],
            created_by=user,
        )
        delivery = WebhookDelivery.objects.create(
            webhook=webhook, event="user.created", payload={}
        )

        deliver_webhook(str(delivery.id))

        delivery.refresh_from_db()
        assert delivery.response_status is None
        assert delivery.next_retry_at is None
        assert "non-public" in delivery.error

    @pytest.mark.django_db
    def test_api_rejects_private_webhook_url(self, auth_headers, user):
        from django.test import Client

        response = Client().post(
            "/api/webhooks/",
            {
                "name": "Metadata",
                "url": "https://169.254.169.254/latest/meta-data/",
                "events": ["user.created"],
            },
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 400
        assert not Webhook.objects.filter(created_by=user).exists()
