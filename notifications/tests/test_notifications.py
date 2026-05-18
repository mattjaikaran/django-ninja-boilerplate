import pytest
from django.contrib.auth import get_user_model

from core.tests.factories import UserFactory
from notifications.models import Notification
from notifications.services import NotificationService, notify

User = get_user_model()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def other_user():
    return UserFactory()


@pytest.fixture
def service():
    return NotificationService()


@pytest.fixture
def notification(user, service):
    return service.create_notification(
        user=user,
        type="in_app",
        title="Test Notification",
        body="Test body",
    )


@pytest.fixture
def auth_headers(user):
    from ninja_jwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}


@pytest.mark.django_db
class TestNotificationModel:
    def test_create_notification(self, user, service):
        n = service.create_notification(
            user=user,
            type="in_app",
            title="Hello",
            body="World",
        )
        assert n.id is not None
        assert n.title == "Hello"
        assert n.body == "World"
        assert n.type == "in_app"
        assert not n.is_read
        assert n.user == user

    def test_mark_read(self, notification):
        assert not notification.is_read
        assert notification.read_at is None
        notification.mark_read()
        notification.refresh_from_db()
        assert notification.is_read
        assert notification.read_at is not None

    def test_str(self, notification):
        expected = f"in_app: Test Notification -> {notification.user_id}"
        assert str(notification) == expected

    def test_notify_convenience_function(self, user):
        n = notify(user=user, type="email", title="Email Title", body="Email body")
        assert n.id is not None
        assert n.type == "email"
        assert Notification.objects.filter(user=user).count() == 1


@pytest.mark.django_db
class TestNotificationService:
    def test_list_notifications(self, user, service):
        service.create_notification(user, "in_app", "N1", "body1")
        service.create_notification(user, "in_app", "N2", "body2")
        qs = service.list_notifications(user)
        assert qs.count() == 2

    def test_list_notifications_unread_only(self, user, service):
        n1 = service.create_notification(user, "in_app", "N1", "body1")
        service.create_notification(user, "in_app", "N2", "body2")
        n1.mark_read()
        qs = service.list_notifications(user, unread_only=True)
        assert qs.count() == 1
        assert qs.first().title == "N2"

    def test_get_unread_count(self, user, service):
        service.create_notification(user, "in_app", "N1", "body1")
        service.create_notification(user, "in_app", "N2", "body2")
        assert service.get_unread_count(user) == 2

    def test_mark_all_read(self, user, service):
        service.create_notification(user, "in_app", "N1", "body1")
        service.create_notification(user, "in_app", "N2", "body2")
        updated = service.mark_all_read(user)
        assert updated == 2
        assert service.get_unread_count(user) == 0

    def test_mark_all_read_only_for_user(self, user, other_user, service):
        service.create_notification(user, "in_app", "N1", "body1")
        service.create_notification(other_user, "in_app", "N2", "body2")
        service.mark_all_read(user)
        assert service.get_unread_count(user) == 0
        assert service.get_unread_count(other_user) == 1

    def test_delete_notification(self, user, notification, service):
        nid = str(notification.id)
        service.delete_notification(nid, user)
        assert not Notification.objects.filter(id=nid).exists()

    def test_get_notification_wrong_user(self, notification, other_user, service):
        from django.http import Http404

        with pytest.raises(Http404):
            service.get_notification(str(notification.id), other_user)


@pytest.mark.django_db
class TestNotificationAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client

        return Client()

    def test_list_notifications(self, api_client, user, auth_headers, service):
        service.create_notification(user, "in_app", "N1", "body1")
        service.create_notification(user, "in_app", "N2", "body2")
        response = api_client.get("/api/notifications/", **auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["unread_count"] == 2
        assert len(data["items"]) == 2

    def test_list_unread_only(self, api_client, user, auth_headers, service):
        n1 = service.create_notification(user, "in_app", "N1", "body1")
        service.create_notification(user, "in_app", "N2", "body2")
        n1.mark_read()
        response = api_client.get(
            "/api/notifications/?unread_only=true", **auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    def test_get_unread_count(self, api_client, user, auth_headers, service):
        service.create_notification(user, "in_app", "N1", "body1")
        response = api_client.get("/api/notifications/unread-count", **auth_headers)
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_mark_all_read(self, api_client, user, auth_headers, service):
        service.create_notification(user, "in_app", "N1", "body1")
        service.create_notification(user, "in_app", "N2", "body2")
        response = api_client.post("/api/notifications/read-all", **auth_headers)
        assert response.status_code == 200
        assert response.json()["updated"] == 2
        assert service.get_unread_count(user) == 0

    def test_mark_single_read(self, api_client, user, auth_headers, notification):
        response = api_client.post(
            f"/api/notifications/{notification.id}/read", **auth_headers
        )
        assert response.status_code == 200
        notification.refresh_from_db()
        assert notification.is_read

    def test_delete_notification(self, api_client, user, auth_headers, notification):
        nid = notification.id
        response = api_client.delete(
            f"/api/notifications/{notification.id}", **auth_headers
        )
        assert response.status_code == 204
        assert not Notification.objects.filter(id=nid).exists()

    def test_cannot_access_other_users_notification(
        self, api_client, other_user, service
    ):
        from ninja_jwt.tokens import RefreshToken

        other_notif = service.create_notification(
            other_user, "in_app", "Secret", "body"
        )
        refresh = RefreshToken.for_user(other_user)
        other_headers = {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}

        attacker = UserFactory()
        attacker_refresh = RefreshToken.for_user(attacker)
        attacker_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {attacker_refresh.access_token}"
        }

        response = api_client.get(
            f"/api/notifications/{other_notif.id}", **attacker_headers
        )
        assert response.status_code == 404
