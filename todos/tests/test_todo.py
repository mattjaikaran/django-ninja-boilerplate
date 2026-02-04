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
    return TodoFactory(user=user)


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
        todo = TodoFactory(user=user)
        assert todo.title
        assert todo.description
        assert not todo.completed
        assert todo.user == user

    def test_todo_str(self, todo):
        assert str(todo) == todo.title

    def test_todo_ordering(self, user):
        """Test that todos are ordered by created_at descending (most recent first)."""
        todo1 = TodoFactory(title="First Todo", user=user)
        todo2 = TodoFactory(title="Second Todo", user=user)

        # Force different timestamps by updating created_at
        from django.utils import timezone
        from datetime import timedelta

        Todo.objects.filter(id=todo1.id).update(created_at=timezone.now() - timedelta(hours=1))
        todo1.refresh_from_db()

        todos = list(Todo.objects.all())
        assert len(todos) == 2
        assert todos[0].id == todo2.id  # Most recent first
        assert todos[1].id == todo1.id


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
            "completed": False,
        }
        response = api_client.post(
            "/api/todos/", todo_data, content_type="application/json", **auth_headers
        )
        assert response.status_code == 201
        assert Todo.objects.filter(user=user).exists()

    def test_list_user_todos(self, api_client, auth_headers, user):
        TodoFactory(title="Todo 1", user=user)
        TodoFactory(title="Todo 2", user=user)

        # Create todo for another user
        other_user = UserFactory()
        TodoFactory(
            title="Other's Todo",
            description="This shouldn't be visible",
            user=other_user,
        )

        response = api_client.get("/api/todos/", **auth_headers)
        assert response.status_code == 200
        todos = response.json()
        assert len(todos) == 2  # Only current user's todos
        assert all(todo["user"] == str(user.id) for todo in todos)

    def test_get_todo(self, api_client, auth_headers, user):
        todo = TodoFactory(title="Test Todo", user=user)
        response = api_client.get(f"/api/todos/{todo.id}", **auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Test Todo"

    def test_update_todo(self, api_client, auth_headers, user):
        todo = TodoFactory(title="Original Title", user=user)
        update_data = {
            "title": "Updated Title",
            "description": "Updated Description",
            "completed": True,
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
        assert todo.completed == update_data["completed"]

    def test_delete_todo(self, api_client, auth_headers, user):
        todo = TodoFactory(user=user)
        response = api_client.delete(f"/api/todos/{todo.id}", **auth_headers)
        assert response.status_code == 204
        assert not Todo.objects.filter(id=todo.id).exists()

    def test_cannot_access_others_todo(self, api_client, auth_headers):
        # Create a todo for another user
        other_user = UserFactory()
        other_todo = TodoFactory(
            title="Other's Todo",
            description="This shouldn't be accessible",
            user=other_user,
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
