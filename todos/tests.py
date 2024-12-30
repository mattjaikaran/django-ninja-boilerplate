import pytest
from django.contrib.auth import get_user_model
from .models import Todo
from core.tests import test_user, auth_headers, create_user

User = get_user_model()


@pytest.fixture
def todo_data():
    return {"title": "Test Todo", "description": "Test Description", "completed": False}


@pytest.fixture
def create_todo(test_user):
    def make_todo(**kwargs):
        todo_data = {
            "title": "Test Todo",
            "description": "Test Description",
            "completed": False,
        }
        todo_data.update(kwargs)
        return Todo.objects.create(user=test_user, **todo_data)

    return make_todo


@pytest.mark.django_db
class TestTodoModel:
    def test_create_todo(self, test_user, todo_data):
        todo = Todo.objects.create(user=test_user, **todo_data)
        assert todo.title == todo_data["title"]
        assert todo.description == todo_data["description"]
        assert not todo.completed
        assert todo.user == test_user

    def test_todo_str(self, create_todo):
        todo = create_todo()
        assert str(todo) == todo.title

    def test_todo_ordering(self, create_todo):
        todo1 = create_todo(title="First Todo")
        todo2 = create_todo(title="Second Todo")
        todos = Todo.objects.all()
        assert todos[0] == todo2  # Most recent first
        assert todos[1] == todo1


@pytest.mark.django_db
class TestTodoAPI:
    @pytest.fixture
    def api_client(self):
        from django.test import Client

        return Client()

    def test_create_todo(self, api_client, todo_data, auth_headers):
        response = api_client.post(
            "/api/todos/", todo_data, content_type="application/json", **auth_headers
        )
        assert response.status_code == 200
        assert Todo.objects.filter(user=test_user).exists()

    def test_list_user_todos(self, api_client, create_todo, auth_headers):
        create_todo(title="Todo 1")
        create_todo(title="Todo 2")

        # Create todo for another user
        other_user = create_user(username="other", email="other@example.com")
        Todo.objects.create(
            user=other_user,
            title="Other's Todo",
            description="This shouldn't be visible",
        )

        response = api_client.get("/api/todos/", **auth_headers)
        assert response.status_code == 200
        todos = response.json()
        assert len(todos) == 2  # Only test_user's todos
        assert all(todo["user_id"] == str(test_user.id) for todo in todos)

    def test_get_todo(self, api_client, create_todo, auth_headers):
        todo = create_todo(title="Test Todo")
        response = api_client.get(f"/api/todos/{todo.id}", **auth_headers)
        assert response.status_code == 200
        assert response.json()["title"] == "Test Todo"

    def test_update_todo(self, api_client, create_todo, auth_headers):
        todo = create_todo(title="Original Title")
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

    def test_delete_todo(self, api_client, create_todo, auth_headers):
        todo = create_todo()
        response = api_client.delete(f"/api/todos/{todo.id}", **auth_headers)
        assert response.status_code == 200
        assert not Todo.objects.filter(id=todo.id).exists()

    def test_cannot_access_others_todo(self, api_client, auth_headers):
        # Create a todo for another user
        other_user = create_user(username="other", email="other@example.com")
        other_todo = Todo.objects.create(
            user=other_user,
            title="Other's Todo",
            description="This shouldn't be accessible",
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
