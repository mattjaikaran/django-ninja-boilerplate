import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from ninja_jwt.tokens import RefreshToken

User = get_user_model()


# Reusable fixtures that can be imported in other test files
@pytest.fixture(scope="session")
def test_password():
    return "TestPass123!"


@pytest.fixture(scope="session")
def test_user_data(test_password):
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": test_password,
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def create_user(test_user_data):
    """Factory fixture to create users with custom data"""

    def make_user(**kwargs):
        user_data = test_user_data.copy()
        user_data.update(kwargs)
        return User.objects.create_user(**user_data)

    return make_user


@pytest.fixture
def test_user(create_user, django_db_setup, django_db_blocker):
    """Create a test user that can be imported in other tests"""
    with django_db_blocker.unblock():
        return create_user()


@pytest.fixture
def auth_token(test_user):
    """Get JWT token for test user"""
    refresh = RefreshToken.for_user(test_user)
    return str(refresh.access_token)


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with JWT token"""
    return {"HTTP_AUTHORIZATION": f"Bearer {auth_token}"}


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self, test_user_data):
        user = User.objects.create_user(**test_user_data)
        assert user.email == test_user_data["email"]
        assert user.username == test_user_data["username"]
        assert user.check_password(test_user_data["password"])
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self, test_user_data):
        user = User.objects.create_superuser(**test_user_data)
        assert user.is_staff
        assert user.is_superuser

    def test_user_str(self, test_user):
        assert str(test_user) == test_user.email

    def test_user_full_name(self, test_user):
        assert test_user.full_name == f"{test_user.first_name} {test_user.last_name}"

    def test_duplicate_email(self, test_user, test_user_data):
        with pytest.raises(ValidationError):
            User.objects.create_user(**test_user_data)

    def test_duplicate_username(self, test_user, test_user_data):
        with pytest.raises(ValidationError):
            User.objects.create_user(**test_user_data)

    def test_email_required(self, test_user_data):
        test_user_data.pop("email")
        with pytest.raises(ValueError):
            User.objects.create_user(**test_user_data)


@pytest.mark.django_db
class TestUserAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client

        return Client()

    def test_signup(self, api_client, test_user_data):
        response = api_client.post(
            "/api/users/signup", test_user_data, content_type="application/json"
        )
        assert response.status_code == 201
        assert User.objects.filter(email=test_user_data["email"]).exists()

    def test_get_user(self, api_client, test_user, auth_headers):
        response = api_client.get(f"/api/users/{test_user.id}", **auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == test_user.email

    def test_list_users(self, api_client, test_user, create_user, auth_headers):
        create_user(username="testuser2", email="test2@example.com")
        response = api_client.get("/api/users/", **auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_update_user(self, api_client, test_user, auth_headers):
        update_data = {
            "username": "updateduser",
            "email": "updated@example.com",
            "first_name": "Updated",
            "last_name": "User",
        }
        response = api_client.put(
            f"/api/users/{test_user.id}",
            update_data,
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        test_user.refresh_from_db()
        assert test_user.username == update_data["username"]

    def test_delete_user(self, api_client, test_user, auth_headers):
        response = api_client.delete(f"/api/users/{test_user.id}", **auth_headers)
        assert response.status_code == 204
        assert not User.objects.filter(id=test_user.id).exists()
