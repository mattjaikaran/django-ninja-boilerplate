import pytest
from django.contrib.auth import get_user_model

from core.tests.factories import UserFactory
from todos.models import Todo
from todos.tests.factories import TodoFactory

User = get_user_model()


@pytest.fixture
def user():
    """Create a test user using factory."""
    return UserFactory()


@pytest.fixture
def todo(user):
    """Create a test todo using factory."""
    return TodoFactory(created_by=user, updated_by=user)


@pytest.fixture
def auth_headers(user):
    """Create auth headers for authenticated requests."""
    from ninja_jwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    access_token = refresh.access_token
    return {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}


@pytest.mark.django_db
class TestTodoModel:
    def test_create_todo(self, user):
        todo = TodoFactory(created_by=user, updated_by=user)
        assert todo.title
        assert todo.description
        assert not todo.is_completed
        assert todo.created_by == user

    def test_todo_str(self, todo):
        assert str(todo) == todo.title

    def test_todo_ordering(self, user):
        todo1 = TodoFactory(title="First Todo", created_by=user, updated_by=user)
        todo2 = TodoFactory(title="Second Todo", created_by=user, updated_by=user)
        todos = Todo.objects.all()
        assert todos[0] == todo2  # Most recent first
        assert todos[1] == todo1


@pytest.mark.django_db
class TestTodoAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client

        return Client()

    def test_create_todo(self, api_client, auth_headers, user):
        todo_data = {
            "title": "New Todo",
            "description": "New Description",
            "is_completed": False,
        }
        response = api_client.post(
            "/api/todos/", todo_data, content_type="application/json", **auth_headers
        )
        assert response.status_code == 201
        assert Todo.objects.filter(created_by=user).exists()

    def test_list_user_todos(self, api_client, auth_headers, user):
        TodoFactory(title="Todo 1", created_by=user, updated_by=user)
        TodoFactory(title="Todo 2", created_by=user, updated_by=user)

        # Create todo for another user
        other_user = UserFactory()
        TodoFactory(
            title="Other's Todo",
            description="This shouldn't be visible",
            created_by=other_user,
            updated_by=other_user,
        )

        response = api_client.get("/api/todos/", **auth_headers)
        assert response.status_code == 200
        todos = response.json()
        assert len(todos) == 2  # Only current user's todos
        assert all(todo["created_by"] == str(user.id) for todo in todos)

    def test_get_todo(self, api_client, auth_headers, user):
        todo = TodoFactory(title="Test Todo", created_by=user, updated_by=user)
        response = api_client.get(f"/api/todos/{todo.id}", **auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Test Todo"

    def test_update_todo(self, api_client, auth_headers, user):
        todo = TodoFactory(title="Original Title", created_by=user, updated_by=user)
        update_data = {
            "title": "Updated Title",
            "description": "Updated Description",
            "is_completed": True,
        }
        response = api_client.put(
            f"/api/todos/{todo.id}",
            update_data,
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 200
        todo.refresh_from_db()
        assert todo.title == update_data["title"]
        assert todo.is_completed == update_data["is_completed"]

    def test_delete_todo(self, api_client, auth_headers, user):
        todo = TodoFactory(created_by=user, updated_by=user)
        response = api_client.delete(f"/api/todos/{todo.id}", **auth_headers)
        assert response.status_code == 204
        assert not Todo.objects.filter(id=todo.id).exists()

    def test_cannot_access_others_todo(self, api_client, auth_headers):
        # Create a todo for another user
        other_user = UserFactory()
        other_todo = TodoFactory(
            title="Other's Todo",
            description="This shouldn't be accessible",
            created_by=other_user,
            updated_by=other_user,
        )

        # Try to get
        response = api_client.get(f"/api/todos/{other_todo.id}", **auth_headers)
        assert response.status_code == 404

        # Try to update
        response = api_client.put(
            f"/api/todos/{other_todo.id}",
            {"title": "Hacked Title"},
            content_type="application/json",
            **auth_headers,
        )
        assert response.status_code == 404

        # Try to delete
        response = api_client.delete(f"/api/todos/{other_todo.id}", **auth_headers)
        assert response.status_code == 404
        assert Todo.objects.filter(id=other_todo.id).exists()
