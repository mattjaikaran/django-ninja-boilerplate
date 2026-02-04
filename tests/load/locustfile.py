"""Locust Load Testing Scenarios.

This module defines load testing scenarios for the Django Ninja API.
Use Locust to simulate concurrent users and measure API performance.

Usage:
    # Start Locust web UI
    locust -f tests/load/locustfile.py --host=http://localhost:8000

    # Run headless
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
        --headless -u 100 -r 10 -t 60s

Environment Variables:
    TEST_USER_EMAIL: Email for authenticated requests
    TEST_USER_PASSWORD: Password for authenticated requests
    LOCUST_HOST: Target host (default: http://localhost:8000)
"""

import os
import random
import string

from locust import HttpUser, between, task
from locust.exception import StopUser


def random_string(length: int = 8) -> str:
    """Generate a random string for test data."""
    return "".join(random.choices(string.ascii_lowercase, k=length))


def random_email() -> str:
    """Generate a random email address."""
    return f"loadtest_{random_string()}@example.com"


# =============================================================================
# Base User Classes
# =============================================================================


class BaseAPIUser(HttpUser):
    """Base class for API load testing users.

    Provides common functionality for all user types.
    """

    abstract = True

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    # Default headers
    default_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    def on_start(self):
        """Initialize user session."""
        self.auth_token = None
        self.user_email = None

    def get_auth_headers(self):
        """Get headers with authentication token."""
        headers = self.default_headers.copy()
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers


# =============================================================================
# Anonymous User Scenarios
# =============================================================================


class AnonymousUser(BaseAPIUser):
    """Simulates anonymous users accessing public endpoints."""

    weight = 3  # 3x more common than authenticated users

    @task(10)
    def health_check(self):
        """Check the health endpoint."""
        self.client.get(
            "/api/health/",
            headers=self.default_headers,
            name="/api/health/",
        )

    @task(5)
    def health_detailed(self):
        """Check the detailed health endpoint."""
        self.client.get(
            "/api/health/detailed/",
            headers=self.default_headers,
            name="/api/health/detailed/",
        )

    @task(2)
    def get_openapi_schema(self):
        """Fetch the OpenAPI schema."""
        self.client.get(
            "/api/openapi.json",
            headers=self.default_headers,
            name="/api/openapi.json",
        )

    @task(1)
    def attempt_login_invalid(self):
        """Simulate failed login attempts (security testing)."""
        with self.client.post(
            "/api/auth/login",
            json={
                "email": random_email(),
                "password": random_string(12),
            },
            headers=self.default_headers,
            name="/api/auth/login [invalid]",
            catch_response=True,
        ) as response:
            # We expect 401 for invalid credentials
            if response.status_code in [400, 401, 422]:
                response.success()


# =============================================================================
# Authenticated User Scenarios
# =============================================================================


class AuthenticatedUser(BaseAPIUser):
    """Simulates authenticated users performing various actions."""

    weight = 1

    def on_start(self):
        """Log in before starting tasks."""
        super().on_start()
        self._login()

    def _login(self):
        """Authenticate the user and get a token."""
        # Try to use environment credentials or create a new user
        email = os.environ.get("TEST_USER_EMAIL", random_email())
        password = os.environ.get("TEST_USER_PASSWORD", "LoadTest123!")

        # First, try to signup (in case user doesn't exist)
        self.client.post(
            "/api/auth/signup",
            json={
                "email": email,
                "password": password,
                "first_name": "Load",
                "last_name": "Tester",
            },
            headers=self.default_headers,
            name="/api/auth/signup [setup]",
        )

        # Then login
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            headers=self.default_headers,
            name="/api/auth/login",
        )

        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get("access") or data.get("token")
            self.user_email = email
        else:
            # Can't authenticate - stop this user
            raise StopUser

    @task(10)
    def get_current_user(self):
        """Fetch current user profile."""
        self.client.get(
            "/api/auth/me",
            headers=self.get_auth_headers(),
            name="/api/auth/me",
        )

    @task(8)
    def list_todos(self):
        """List all todos for the user."""
        self.client.get(
            "/api/todos/",
            headers=self.get_auth_headers(),
            name="/api/todos/",
        )

    @task(5)
    def create_todo(self):
        """Create a new todo item."""
        response = self.client.post(
            "/api/todos/",
            json={
                "title": f"Load Test Todo {random_string()}",
                "description": f"Created during load test: {random_string(20)}",
                "is_completed": False,
            },
            headers=self.get_auth_headers(),
            name="/api/todos/ [create]",
        )

        # Store the todo ID for later operations
        if response.status_code in [200, 201]:
            data = response.json()
            todo_id = data.get("id")
            if todo_id:
                self.created_todo_ids = getattr(self, "created_todo_ids", [])
                self.created_todo_ids.append(todo_id)

    @task(3)
    def get_single_todo(self):
        """Fetch a single todo item."""
        todo_ids = getattr(self, "created_todo_ids", [])
        if not todo_ids:
            return

        todo_id = random.choice(todo_ids)
        self.client.get(
            f"/api/todos/{todo_id}/",
            headers=self.get_auth_headers(),
            name="/api/todos/[id]/",
        )

    @task(2)
    def update_todo(self):
        """Update an existing todo."""
        todo_ids = getattr(self, "created_todo_ids", [])
        if not todo_ids:
            return

        todo_id = random.choice(todo_ids)
        self.client.patch(
            f"/api/todos/{todo_id}/",
            json={
                "title": f"Updated Todo {random_string()}",
                "is_completed": random.choice([True, False]),
            },
            headers=self.get_auth_headers(),
            name="/api/todos/[id]/ [update]",
        )

    @task(1)
    def delete_todo(self):
        """Delete a todo item."""
        todo_ids = getattr(self, "created_todo_ids", [])
        if not todo_ids:
            return

        todo_id = todo_ids.pop()
        self.client.delete(
            f"/api/todos/{todo_id}/",
            headers=self.get_auth_headers(),
            name="/api/todos/[id]/ [delete]",
        )


# =============================================================================
# Admin User Scenarios
# =============================================================================


class AdminUser(BaseAPIUser):
    """Simulates admin users performing administrative actions."""

    weight = 0  # Disabled by default, enable with --users-per-class

    def on_start(self):
        """Log in as admin before starting tasks."""
        super().on_start()
        self._login_admin()

    def _login_admin(self):
        """Authenticate as admin user."""
        email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        password = os.environ.get("ADMIN_PASSWORD", "adminpass123")

        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            headers=self.default_headers,
            name="/api/auth/login [admin]",
        )

        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get("access") or data.get("token")
        else:
            raise StopUser

    @task(5)
    def list_all_users(self):
        """List all users (admin only)."""
        self.client.get(
            "/api/users/",
            headers=self.get_auth_headers(),
            name="/api/users/ [admin]",
        )


# =============================================================================
# Stress Test Scenarios
# =============================================================================


class StressTestUser(BaseAPIUser):
    """High-frequency user for stress testing."""

    weight = 0  # Disabled by default

    # Minimal wait time for stress testing
    wait_time = between(0.1, 0.5)

    @task(1)
    def rapid_health_check(self):
        """Rapid health checks for stress testing."""
        self.client.get(
            "/api/health/",
            headers=self.default_headers,
            name="/api/health/ [stress]",
        )


# =============================================================================
# Custom Load Test Shapes
# =============================================================================


class StagesLoadTestShape:
    """Custom load test shape with multiple stages.

    To use, run: locust -f locustfile.py --headless
    """

    stages = [
        # Ramp up
        {"duration": 60, "users": 10, "spawn_rate": 1},
        {"duration": 120, "users": 50, "spawn_rate": 5},
        {"duration": 180, "users": 100, "spawn_rate": 10},
        # Peak load
        {"duration": 300, "users": 100, "spawn_rate": 10},
        # Ramp down
        {"duration": 360, "users": 50, "spawn_rate": 5},
        {"duration": 420, "users": 10, "spawn_rate": 1},
    ]

    def tick(self):
        """Return the current stage configuration."""
        import time

        run_time = time.time() - self.start_time

        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])

        return None


# =============================================================================
# Event Hooks
# =============================================================================


from locust import events


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts."""
    print("=" * 60)
    print("Load Test Starting")
    print(f"Target Host: {environment.host}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops."""
    print("=" * 60)
    print("Load Test Completed")
    print("=" * 60)

    # Print summary statistics
    stats = environment.stats
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Failed requests: {stats.total.num_failures}")
    if stats.total.num_requests > 0:
        failure_rate = (stats.total.num_failures / stats.total.num_requests) * 100
        print(f"Failure rate: {failure_rate:.2f}%")
    print(f"Median response time: {stats.total.median_response_time}ms")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
