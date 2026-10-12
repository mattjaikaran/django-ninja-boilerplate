import pytest
from django.contrib.auth import get_user_model

from core.tests.factories import UserFactory

User = get_user_model()


@pytest.fixture
def user():
    """Create a test user using factory."""
    return UserFactory()


@pytest.fixture
def user_with_password():
    """Create a staff test user with a known password (user admin requires staff)."""
    return UserFactory(is_staff=True, set_password="testpass123")


@pytest.mark.django_db
class TestUserAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client

        return Client()

    @pytest.fixture
    def auth_headers(self, user_with_password):
        """Create auth headers for authenticated requests."""
        from ninja_jwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user_with_password)
        access_token = refresh.access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}

    def test_get_user(self, api_client, user, auth_headers):
        response = api_client.get(f"/api/users/{user.id}", **auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_update_user(self, api_client, user, auth_headers):
        update_data = {
            "username": "updateduser",
            "email": "updated@example.com",
            "first_name": "Updated",
            "last_name": "User",
        }
        response = api_client.put(
            f"/api/users/{user.id}",
            update_data,
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.username == update_data["username"]

    def test_update_user_persists_multi_word_fields(
        self, api_client, user, auth_headers
    ):
        """A camelCase body updates multi-word model fields such as first_name."""
        response = api_client.put(
            f"/api/users/{user.id}",
            {"firstName": "Ada", "lastName": "Lovelace", "emailNotifications": False},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.first_name == "Ada"
        assert user.last_name == "Lovelace"
        assert user.email_notifications is False
        assert response.json()["firstName"] == "Ada"

    def test_delete_user(self, api_client, user, auth_headers):
        response = api_client.delete(f"/api/users/{user.id}", **auth_headers)
        assert response.status_code == 204
        assert not User.objects.filter(id=user.id).exists()
