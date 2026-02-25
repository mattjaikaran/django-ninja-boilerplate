#!/usr/bin/env python
"""E2E Test Generator

This script generates pytest test stubs from user journey YAML definitions.
It reads user journeys from tests/user_journeys.yaml and generates
corresponding test files in tests/e2e/ directory.

Usage:
    python scripts/generate_e2e_tests.py
    python scripts/generate_e2e_tests.py --input tests/user_journeys.yaml
    python scripts/generate_e2e_tests.py --output tests/e2e/
    python scripts/generate_e2e_tests.py --dry-run
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    print("Error: PyYAML is required. Install with: uv add pyyaml")
    sys.exit(1)

try:
    from jinja2 import BaseLoader, Environment
except ImportError:
    print("Error: Jinja2 is required. Install with: uv add jinja2")
    sys.exit(1)


# =============================================================================
# Jinja2 Templates
# =============================================================================

TEST_FILE_TEMPLATE = '''"""
E2E Tests for {{ journey.name }}

Auto-generated from user journey definitions.
Generated at: {{ generated_at }}

Journey: {{ journey.name }}
Description: {{ journey.description }}

This file contains test stubs that need to be filled in with actual
implementation. The structure and test cases are derived from the
user journey YAML definition.
"""

import pytest
from django.test import Client


{% if journey.fixtures %}
# =============================================================================
# Fixtures
# =============================================================================

{% for fixture in journey.fixtures %}
@pytest.fixture
def {{ fixture.name }}({% if fixture.dependencies %}{{ fixture.dependencies | join(', ') }}{% endif %}):
    """{{ fixture.description | default('Fixture for ' + fixture.name) }}"""
    # TODO: Implement fixture
    {% if fixture.returns %}
    # Expected return: {{ fixture.returns }}
    {% endif %}
    pass

{% endfor %}
{% endif %}

# =============================================================================
# Test Class: {{ journey.name | replace(' ', '') }}
# =============================================================================


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class Test{{ journey.class_name }}:
    """
    E2E tests for: {{ journey.name }}

    {{ journey.description }}

    {% if journey.preconditions %}
    Preconditions:
    {% for precondition in journey.preconditions %}
    - {{ precondition }}
    {% endfor %}
    {% endif %}

    {% if journey.postconditions %}
    Postconditions:
    {% for postcondition in journey.postconditions %}
    - {{ postcondition }}
    {% endfor %}
    {% endif %}
    """

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test fixtures."""
        self.client = Client()
        # TODO: Add any additional setup here

{% for step in journey.steps %}
    # -------------------------------------------------------------------------
    # Step {{ loop.index }}: {{ step.name }}
    # -------------------------------------------------------------------------

    def test_step_{{ loop.index }}_{{ step.name | slugify }}(self{% if step.fixtures %}, {{ step.fixtures | join(', ') }}{% endif %}):
        """
        Step {{ loop.index }}: {{ step.name }}

        {{ step.description | default('') }}

        {% if step.action %}
        Action: {{ step.action }}
        {% endif %}
        {% if step.expected %}
        Expected: {{ step.expected }}
        {% endif %}
        {% if step.endpoint %}
        Endpoint: {{ step.endpoint }}
        {% endif %}
        """
        # TODO: Implement this test step
        {% if step.endpoint %}
        # Endpoint: {{ step.method | default('GET') }} {{ step.endpoint }}
        {% if step.payload %}
        payload = {{ step.payload | pprint }}
        {% endif %}
        {% if step.method == 'POST' %}
        response = self.client.post(
            "{{ step.endpoint }}",
            {% if step.payload %}payload,{% endif %}
            content_type="application/json",
            {% if step.auth_required %}**auth_headers,{% endif %}
        )
        {% elif step.method == 'PUT' %}
        response = self.client.put(
            "{{ step.endpoint }}",
            {% if step.payload %}payload,{% endif %}
            content_type="application/json",
            {% if step.auth_required %}**auth_headers,{% endif %}
        )
        {% elif step.method == 'PATCH' %}
        response = self.client.patch(
            "{{ step.endpoint }}",
            {% if step.payload %}payload,{% endif %}
            content_type="application/json",
            {% if step.auth_required %}**auth_headers,{% endif %}
        )
        {% elif step.method == 'DELETE' %}
        response = self.client.delete(
            "{{ step.endpoint }}",
            {% if step.auth_required %}**auth_headers,{% endif %}
        )
        {% else %}
        response = self.client.get(
            "{{ step.endpoint }}",
            {% if step.auth_required %}**auth_headers,{% endif %}
        )
        {% endif %}
        {% if step.expected_status %}
        assert response.status_code == {{ step.expected_status }}
        {% endif %}
        {% endif %}
        {% if step.assertions %}
        # Assertions:
        {% for assertion in step.assertions %}
        # - {{ assertion }}
        {% endfor %}
        {% endif %}
        pytest.skip("TODO: Implement this test step")

{% endfor %}

    # -------------------------------------------------------------------------
    # Full Journey Test (all steps in sequence)
    # -------------------------------------------------------------------------

    def test_full_journey(self{% if journey.all_fixtures %}, {{ journey.all_fixtures | join(', ') }}{% endif %}):
        """
        Complete journey test: {{ journey.name }}

        This test runs through all steps of the journey in sequence.
        Use this for true end-to-end validation of the entire flow.
        """
        # TODO: Implement the complete journey
{% for step in journey.steps %}
        # Step {{ loop.index }}: {{ step.name }}
        # {{ step.action | default(step.description | default('')) }}
{% endfor %}
        pytest.skip("TODO: Implement full journey test")
'''

CONFTEST_TEMPLATE = '''"""
E2E Test Configuration and Fixtures

This module provides common fixtures and configuration for E2E tests.
"""

import pytest
from django.test import Client


# =============================================================================
# API Client Fixtures
# =============================================================================


@pytest.fixture
def e2e_client():
    """
    Return a Django test client configured for E2E testing.

    This client maintains session state between requests,
    making it suitable for testing multi-step user journeys.
    """
    return Client()


@pytest.fixture
def authenticated_e2e_client(e2e_client, test_user, auth_token):
    """
    Return an authenticated E2E client.

    The client has the auth token set in its default headers.
    """
    e2e_client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {auth_token}"
    return e2e_client


# =============================================================================
# User Fixtures
# =============================================================================


@pytest.fixture
def test_user_data():
    """Return data for creating a test user."""
    return {
        "email": "e2e_test@example.com",
        "password": "TestPassword123!",
        "first_name": "E2E",
        "last_name": "Tester",
    }


@pytest.fixture
def test_user(db, test_user_data):
    """
    Create and return a test user for E2E tests.

    Returns:
        User: A test user instance
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    # Clean up any existing test user
    User.objects.filter(email=test_user_data["email"]).delete()

    user = User.objects.create_user(
        email=test_user_data["email"],
        password=test_user_data["password"],
        first_name=test_user_data["first_name"],
        last_name=test_user_data["last_name"],
    )
    return user


@pytest.fixture
def auth_token(test_user):
    """
    Get an authentication token for the test user.

    Returns:
        str: JWT access token
    """
    try:
        from ninja_jwt.tokens import RefreshToken
    except ImportError:
        from django_ninja_jwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(test_user)
    return str(refresh.access_token)


@pytest.fixture
def auth_headers(auth_token):
    """
    Return authentication headers for API requests.

    Returns:
        dict: Headers with JWT token
    """
    return {"HTTP_AUTHORIZATION": f"Bearer {auth_token}"}


# =============================================================================
# Todo Fixtures (for CRUD operation tests)
# =============================================================================


@pytest.fixture
def test_todo_data():
    """Return data for creating a test todo."""
    return {
        "title": "E2E Test Todo",
        "description": "This is a test todo for E2E testing",
        "is_completed": False,
    }


@pytest.fixture
def test_todo(db, test_user, test_todo_data):
    """
    Create and return a test todo for E2E tests.

    Returns:
        Todo: A test todo instance
    """
    from todos.models import Todo

    todo = Todo.objects.create(
        title=test_todo_data["title"],
        description=test_todo_data["description"],
        is_completed=test_todo_data["is_completed"],
        created_by=test_user,
        updated_by=test_user,
    )
    return todo


# =============================================================================
# Helper Fixtures
# =============================================================================


@pytest.fixture
def unique_email():
    """
    Generate a unique email for testing.

    Returns:
        str: A unique email address
    """
    import uuid
    return f"e2e_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def mock_email_backend(settings):
    """
    Configure email backend to use in-memory storage during tests.

    This prevents actual emails from being sent and allows
    inspection of sent emails.
    """
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail
    mail.outbox = []
    return mail


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_sequences(db):
    """
    Reset database sequences after each test.

    This ensures consistent ID generation across tests.
    """
    yield
    # Cleanup happens automatically with transaction rollback


@pytest.fixture
def clean_db(db):
    """
    Provide a clean database state.

    Use this fixture when you need to ensure no residual data
    from previous tests.
    """
    from django.contrib.auth import get_user_model
    from todos.models import Todo

    User = get_user_model()

    # Clean up test data
    Todo.objects.filter(title__startswith="E2E").delete()
    User.objects.filter(email__startswith="e2e_test").delete()

    yield

    # Post-test cleanup
    Todo.objects.filter(title__startswith="E2E").delete()
    User.objects.filter(email__startswith="e2e_test").delete()


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config):
    """Register custom markers for E2E tests."""
    config.addinivalue_line(
        "markers",
        "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers",
        "journey(name): mark test as part of a specific user journey"
    )
'''


# =============================================================================
# Helper Functions
# =============================================================================


def slugify(text: str) -> str:
    """Convert text to a valid Python identifier."""
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special characters with underscores
    text = re.sub(r"[^a-z0-9]+", "_", text)
    # Remove leading/trailing underscores
    text = text.strip("_")
    # Ensure it doesn't start with a number
    if text and text[0].isdigit():
        text = "_" + text
    return text


def to_class_name(text: str) -> str:
    """Convert text to a valid Python class name (PascalCase)."""
    # Split on spaces and special characters
    words = re.split(r"[^a-zA-Z0-9]+", text)
    # Capitalize each word and join
    return "".join(word.capitalize() for word in words if word)


def pprint_dict(obj: Any) -> str:
    """Pretty print a dictionary for Python code."""
    if isinstance(obj, dict):
        items = ", ".join(
            f'"{k}": "{v}"' if isinstance(v, str) else f'"{k}": {v}'
            for k, v in obj.items()
        )
        return "{" + items + "}"
    return str(obj)


# =============================================================================
# Journey Parser
# =============================================================================


class JourneyParser:
    """Parse and validate user journey YAML files."""

    def __init__(self, yaml_path: Path):
        self.yaml_path = yaml_path
        self.journeys: list[dict[str, Any]] = []

    def parse(self) -> list[dict]:
        """Parse the YAML file and return list of journeys."""
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"User journeys file not found: {self.yaml_path}")

        with open(self.yaml_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("Empty YAML file")

        # Handle both single journey and multiple journeys
        if "journeys" in data:
            raw_journeys = data["journeys"]
        elif "journey" in data:
            raw_journeys = [data["journey"]]
        elif isinstance(data, list):
            raw_journeys = data
        else:
            # Assume it's a single journey
            raw_journeys = [data]

        for raw_journey in raw_journeys:
            journey = self._normalize_journey(raw_journey)
            self.journeys.append(journey)

        return self.journeys

    def _normalize_journey(self, raw: dict) -> dict:
        """Normalize a raw journey dict to standard format."""
        journey = {
            "name": raw.get("name", "Unnamed Journey"),
            "description": raw.get("description", ""),
            "class_name": to_class_name(raw.get("name", "UnnamedJourney")),
            "file_name": slugify(raw.get("name", "unnamed_journey")),
            "preconditions": raw.get("preconditions", []),
            "postconditions": raw.get("postconditions", []),
            "fixtures": raw.get("fixtures", []),
            "steps": [],
            "all_fixtures": set(),
        }

        # Process steps
        for step in raw.get("steps", []):
            normalized_step = {
                "name": step.get("name", "Unnamed Step"),
                "description": step.get("description", ""),
                "action": step.get("action", ""),
                "expected": step.get("expected", ""),
                "endpoint": step.get("endpoint", ""),
                "method": step.get("method", "GET").upper(),
                "payload": step.get("payload", {}),
                "expected_status": step.get("expected_status"),
                "auth_required": step.get("auth_required", False),
                "fixtures": step.get("fixtures", []),
                "assertions": step.get("assertions", []),
            }
            journey["steps"].append(normalized_step)

            # Collect all fixtures used
            for fixture in normalized_step["fixtures"]:
                journey["all_fixtures"].add(fixture)

        journey["all_fixtures"] = list(journey["all_fixtures"])

        return journey


# =============================================================================
# Test Generator
# =============================================================================


class E2ETestGenerator:
    """Generate pytest test files from user journeys."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.env = Environment(loader=BaseLoader())

        # Add custom filters
        self.env.filters["slugify"] = slugify
        self.env.filters["pprint"] = pprint_dict

    def generate(self, journeys: list[dict], dry_run: bool = False) -> list[Path]:
        """Generate test files for all journeys."""
        generated_files = []

        # Ensure output directory exists
        if not dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        for journey in journeys:
            file_path = self._generate_journey_test(journey, dry_run)
            generated_files.append(file_path)

        return generated_files

    def _generate_journey_test(self, journey: dict, dry_run: bool) -> Path:
        """Generate a test file for a single journey."""
        template = self.env.from_string(TEST_FILE_TEMPLATE)

        content = template.render(
            journey=journey,
            generated_at=datetime.now().isoformat(),
        )

        file_name = f"test_{journey['file_name']}.py"
        file_path = self.output_dir / file_name

        if dry_run:
            print(f"\n{'=' * 60}")
            print(f"Would generate: {file_path}")
            print("=" * 60)
            print(content)
        else:
            with open(file_path, "w") as f:
                f.write(content)
            print(f"Generated: {file_path}")

        return file_path

    def generate_conftest(self, dry_run: bool = False) -> Path:
        """Generate the conftest.py file."""
        template = self.env.from_string(CONFTEST_TEMPLATE)
        content = template.render()

        file_path = self.output_dir / "conftest.py"

        if dry_run:
            print(f"\n{'=' * 60}")
            print(f"Would generate: {file_path}")
            print("=" * 60)
            print(content)
        else:
            with open(file_path, "w") as f:
                f.write(content)
            print(f"Generated: {file_path}")

        return file_path

    def generate_init(self, dry_run: bool = False) -> Path:
        """Generate the __init__.py file."""
        file_path = self.output_dir / "__init__.py"
        content = '"""E2E Tests package."""\n'

        if dry_run:
            print(f"\n{'=' * 60}")
            print(f"Would generate: {file_path}")
            print("=" * 60)
        else:
            with open(file_path, "w") as f:
                f.write(content)
            print(f"Generated: {file_path}")

        return file_path


# =============================================================================
# Main
# =============================================================================


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate E2E test stubs from user journey YAML definitions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/generate_e2e_tests.py
    python scripts/generate_e2e_tests.py --input tests/user_journeys.yaml
    python scripts/generate_e2e_tests.py --output tests/e2e/
    python scripts/generate_e2e_tests.py --dry-run
        """,
    )

    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("tests/user_journeys.yaml"),
        help="Path to the user journeys YAML file (default: tests/user_journeys.yaml)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("tests/e2e"),
        help="Output directory for generated tests (default: tests/e2e)",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Print generated files without writing them",
    )

    parser.add_argument(
        "--skip-conftest",
        action="store_true",
        help="Skip generating conftest.py (useful if you have a custom one)",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Print header
    print("=" * 60)
    print("E2E Test Generator")
    print("=" * 60)
    print(f"Input:  {args.input}")
    print(f"Output: {args.output}")
    if args.dry_run:
        print("Mode:   DRY RUN (no files will be written)")
    print("=" * 60)

    try:
        # Parse journeys
        print("\nParsing user journeys...")
        journey_parser = JourneyParser(args.input)
        journeys = journey_parser.parse()
        print(f"Found {len(journeys)} journey(s)")

        for journey in journeys:
            print(f"  - {journey['name']} ({len(journey['steps'])} steps)")

        # Generate tests
        print("\nGenerating tests...")
        generator = E2ETestGenerator(args.output)

        # Generate __init__.py
        generator.generate_init(args.dry_run)

        # Generate conftest.py
        if not args.skip_conftest:
            generator.generate_conftest(args.dry_run)

        # Generate journey tests
        generated = generator.generate(journeys, args.dry_run)

        # Summary
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Generated {len(generated)} test file(s)")
        if not args.dry_run:
            print("\nNext steps:")
            print("1. Review the generated test files")
            print("2. Fill in the TODO sections with actual test logic")
            print("3. Run tests with: pytest tests/e2e/ -v")
        print("=" * 60)

    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("\nMake sure to create the user_journeys.yaml file first.")
        print("You can copy tests/user_journeys.example.yaml as a starting point:")
        print("  cp tests/user_journeys.example.yaml tests/user_journeys.yaml")
        sys.exit(1)

    except Exception as e:
        print(f"\nError: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
