from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Todo
from ninja.testing import TestClient

User = get_user_model()


class TodoAPITest(TestCase):
    def setUp(self):
        self.client = TestClient(api)
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="password"
        )
        response = self.client.post(
            "/api/login", {"username": "testuser", "password": "password"}
        )
        self.token = response.json().get("access")
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_create_todo(self):
        response = self.client.post(
            "/api/todos",
            {"title": "Test Todo", "description": "Test Description"},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Test Todo")

    def test_list_todos(self):
        Todo.objects.create(user=self.user, title="Todo 1")
        response = self.client.get("/api/todos", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_update_todo(self):
        todo = Todo.objects.create(user=self.user, title="Old Title")
        response = self.client.put(
            f"/api/todos/{todo.id}", {"title": "New Title"}, headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "New Title")

    def test_delete_todo(self):
        todo = Todo.objects.create(user=self.user, title="To be deleted")
        response = self.client.delete(
            f"/api/todos/{todo.id}", headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Todo.objects.filter(id=todo.id).exists())

    def test_signup(self):
        response = self.client.post(
            "/api/signup",
            {
                "username": "newuser",
                "email": "new@example.com",
                "password": "newpassword",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_login(self):
        response = self.client.post(
            "/api/login", {"username": "testuser", "password": "password"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
