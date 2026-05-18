import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from core.tests.factories import UserFactory

User = get_user_model()


@pytest.fixture
def user():
    """Create a test user using factory."""
    return UserFactory()


@pytest.fixture
def user_with_password():
    """Create a test user with a known password."""
    return UserFactory(set_password="testpass123")


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        user = UserFactory()
        assert user.email
        assert user.username
        assert user.check_password("testpass123")
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self):
        from core.tests.factories import SuperUserFactory

        user = SuperUserFactory()
        assert user.is_staff
        assert user.is_superuser

    def test_user_str(self, user):
        assert str(user) == user.email

    def test_user_full_name(self, user):
        assert user.full_name == f"{user.first_name} {user.last_name}"

    def test_duplicate_email(self, user):
        with pytest.raises(IntegrityError):
            UserFactory(email=user.email)

    def test_duplicate_username(self, user):
        with pytest.raises(IntegrityError):
            UserFactory(username=user.username)

    def test_email_required(self):
        with pytest.raises(ValueError):
            User.objects.create_user(username="test", password="test")  # type: ignore[attr-defined]


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

    def test_signup(self, api_client):
        user_data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "testpass123",
            "first_name": "New",
            "last_name": "User",
        }
        response = api_client.post(
            "/api/auth/signup", user_data, content_type="application/json"
        )
        assert response.status_code == 201
        assert User.objects.filter(email=user_data["email"]).exists()

    def test_get_user(self, api_client, user, auth_headers):
        response = api_client.get(f"/api/users/{user.id}", **auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_list_users(self, api_client, auth_headers):
        UserFactory()  # Create second user
        response = api_client.get("/api/users/", **auth_headers)
        assert response.status_code == 200
        # auth_headers creates user_with_password, plus the UserFactory user = 2 users
        assert len(response.json()) == 2

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

    def test_delete_user(self, api_client, user, auth_headers):
        response = api_client.delete(f"/api/users/{user.id}", **auth_headers)
        assert response.status_code == 204
        assert not User.objects.filter(id=user.id).exists()
