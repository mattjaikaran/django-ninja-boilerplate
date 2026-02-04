"""Base Factory Utilities for Testing.

This module provides base factory classes and utilities for generating test data.
It complements the app-specific factories in core/tests/factories/ and todos/tests/factories/.

Usage:
    from tests.utils.factories import BaseTestFactory, TestDataGenerator

    # Generate random data
    generator = TestDataGenerator()
    email = generator.email()
    password = generator.password()

    # Use in tests
    def test_user_creation():
        data = {
            "email": TestDataGenerator().email(),
            "password": TestDataGenerator().password(),
        }
"""

from __future__ import annotations

import random
import string
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from faker import Faker

fake = Faker()


class TestDataGenerator:
    """Utility class for generating test data.

    Provides methods for generating common test data types like emails,
    passwords, and random strings. Useful when you need data but don't
    need full factory functionality.
    """

    def __init__(self, seed: int | None = None):
        """Initialize the generator.

        Args:
            seed: Optional seed for reproducible data generation.
        """
        if seed is not None:
            Faker.seed(seed)
            random.seed(seed)
        self.faker = Faker()

    # =========================================================================
    # String Generation
    # =========================================================================

    def random_string(self, length: int = 10, charset: str | None = None) -> str:
        """Generate a random string.

        Args:
            length: Length of the string.
            charset: Character set to use. Defaults to lowercase letters.

        Returns:
            str: Random string.
        """
        charset = charset or string.ascii_lowercase
        return "".join(random.choices(charset, k=length))

    def uuid(self) -> str:
        """Generate a random UUID string.

        Returns:
            str: UUID string.
        """
        return str(uuid.uuid4())

    def slug(self, words: int = 3) -> str:
        """Generate a URL-safe slug.

        Args:
            words: Number of words in the slug.

        Returns:
            str: Hyphenated slug string.
        """
        return "-".join(self.faker.words(words))

    # =========================================================================
    # User Data
    # =========================================================================

    def email(self, domain: str = "example.com") -> str:
        """Generate a unique email address.

        Args:
            domain: Email domain to use.

        Returns:
            str: Email address.
        """
        unique_id = self.random_string(8)
        return f"test_{unique_id}@{domain}"

    def password(self, length: int = 12, special_chars: bool = True) -> str:
        """Generate a strong password.

        Args:
            length: Minimum password length.
            special_chars: Whether to include special characters.

        Returns:
            str: Password string.
        """
        chars = string.ascii_letters + string.digits
        if special_chars:
            chars += "!@#$%^&*"

        # Ensure at least one of each character type
        password = [
            random.choice(string.ascii_uppercase),
            random.choice(string.ascii_lowercase),
            random.choice(string.digits),
        ]
        if special_chars:
            password.append(random.choice("!@#$%^&*"))

        # Fill the rest
        remaining_length = max(length - len(password), 0)
        password.extend(random.choices(chars, k=remaining_length))

        # Shuffle and return
        random.shuffle(password)
        return "".join(password)

    def username(self, prefix: str = "") -> str:
        """Generate a username.

        Args:
            prefix: Optional prefix for the username.

        Returns:
            str: Username string.
        """
        base = f"{self.faker.first_name().lower()}{random.randint(100, 999)}"
        return f"{prefix}{base}" if prefix else base

    def first_name(self) -> str:
        """Generate a first name.

        Returns:
            str: First name.
        """
        return self.faker.first_name()

    def last_name(self) -> str:
        """Generate a last name.

        Returns:
            str: Last name.
        """
        return self.faker.last_name()

    def full_name(self) -> str:
        """Generate a full name.

        Returns:
            str: Full name.
        """
        return self.faker.name()

    def phone(self, country_code: str = "+1") -> str:
        """Generate a phone number.

        Args:
            country_code: Country code prefix.

        Returns:
            str: Phone number string.
        """
        return f"{country_code}{random.randint(2000000000, 9999999999)}"

    # =========================================================================
    # Content Data
    # =========================================================================

    def sentence(self, words: int | None = None) -> str:
        """Generate a sentence.

        Args:
            words: Number of words. Random if not specified.

        Returns:
            str: Sentence string.
        """
        if words:
            return self.faker.sentence(nb_words=words)
        return self.faker.sentence()

    def paragraph(self, sentences: int | None = None) -> str:
        """Generate a paragraph.

        Args:
            sentences: Number of sentences. Random if not specified.

        Returns:
            str: Paragraph string.
        """
        if sentences:
            return self.faker.paragraph(nb_sentences=sentences)
        return self.faker.paragraph()

    def text(self, max_length: int = 200) -> str:
        """Generate text content.

        Args:
            max_length: Maximum length of the text.

        Returns:
            str: Text string.
        """
        return self.faker.text(max_nb_chars=max_length)

    def title(self, words: int = 4) -> str:
        """Generate a title.

        Args:
            words: Number of words in the title.

        Returns:
            str: Title string.
        """
        return " ".join(word.capitalize() for word in self.faker.words(words))

    # =========================================================================
    # Date/Time Data
    # =========================================================================

    def datetime_in_past(self, days: int = 30) -> datetime:
        """Generate a datetime in the past.

        Args:
            days: Maximum days in the past.

        Returns:
            datetime: Past datetime.
        """
        delta = timedelta(days=random.randint(1, days))
        return datetime.now(UTC) - delta

    def datetime_in_future(self, days: int = 30) -> datetime:
        """Generate a datetime in the future.

        Args:
            days: Maximum days in the future.

        Returns:
            datetime: Future datetime.
        """
        delta = timedelta(days=random.randint(1, days))
        return datetime.now(UTC) + delta

    def date_of_birth(self, min_age: int = 18, max_age: int = 80) -> datetime:
        """Generate a date of birth.

        Args:
            min_age: Minimum age in years.
            max_age: Maximum age in years.

        Returns:
            datetime: Date of birth.
        """
        return self.faker.date_of_birth(minimum_age=min_age, maximum_age=max_age)

    # =========================================================================
    # Address Data
    # =========================================================================

    def address(self) -> dict[str, str]:
        """Generate an address.

        Returns:
            dict: Address data.
        """
        return {
            "street": self.faker.street_address(),
            "city": self.faker.city(),
            "state": self.faker.state_abbr(),
            "zip_code": self.faker.zipcode(),
            "country": "US",
        }

    def city(self) -> str:
        """Generate a city name.

        Returns:
            str: City name.
        """
        return self.faker.city()

    def country(self) -> str:
        """Generate a country name.

        Returns:
            str: Country name.
        """
        return self.faker.country()

    # =========================================================================
    # Web Data
    # =========================================================================

    def url(self, scheme: str = "https") -> str:
        """Generate a URL.

        Args:
            scheme: URL scheme (http/https).

        Returns:
            str: URL string.
        """
        return f"{scheme}://{self.faker.domain_name()}/{self.slug()}"

    def image_url(self, width: int = 400, height: int = 300) -> str:
        """Generate a placeholder image URL.

        Args:
            width: Image width.
            height: Image height.

        Returns:
            str: Image URL.
        """
        return f"https://picsum.photos/{width}/{height}"

    # =========================================================================
    # Collection Generators
    # =========================================================================

    def choice(self, items: list[Any]) -> Any:
        """Choose a random item from a list.

        Args:
            items: List of items to choose from.

        Returns:
            Any: Random item from the list.
        """
        return random.choice(items)

    def choices(self, items: list[Any], k: int = 3) -> list[Any]:
        """Choose multiple random items from a list.

        Args:
            items: List of items to choose from.
            k: Number of items to choose.

        Returns:
            list: List of random items.
        """
        return random.choices(items, k=min(k, len(items)))

    def sample(self, items: list[Any], k: int = 3) -> list[Any]:
        """Choose unique random items from a list.

        Args:
            items: List of items to choose from.
            k: Number of items to choose.

        Returns:
            list: List of unique random items.
        """
        return random.sample(items, k=min(k, len(items)))


class BaseTestFactory:
    """Base class for custom test factories.

    Provides common patterns and utilities for factory classes.
    Complements Factory Boy factories with more flexibility.
    """

    # Override in subclasses
    model = None
    generator = TestDataGenerator()

    @classmethod
    def build(cls, **kwargs) -> dict[str, Any]:
        """Build a dictionary of attributes without creating a model instance.

        Override get_defaults() in subclasses to provide default values.

        Args:
            **kwargs: Override default attribute values.

        Returns:
            dict: Dictionary of attributes.
        """
        defaults = cls.get_defaults()
        defaults.update(kwargs)
        return defaults

    @classmethod
    def create(cls, **kwargs) -> Any:
        """Create and save a model instance.

        Args:
            **kwargs: Override default attribute values.

        Returns:
            Model instance.

        Raises:
            ValueError: If model class is not set.
        """
        if cls.model is None:
            msg = "model class must be set"
            raise ValueError(msg)

        data = cls.build(**kwargs)
        return cls.model.objects.create(**data)

    @classmethod
    def create_batch(cls, count: int, **kwargs) -> list[Any]:
        """Create multiple model instances.

        Args:
            count: Number of instances to create.
            **kwargs: Override default attribute values for all instances.

        Returns:
            list: List of created instances.
        """
        return [cls.create(**kwargs) for _ in range(count)]

    @classmethod
    def get_defaults(cls) -> dict[str, Any]:
        """Get default attribute values.

        Override in subclasses to provide model-specific defaults.

        Returns:
            dict: Default attribute values.
        """
        return {}


# =============================================================================
# Example Factory Implementation
# =============================================================================


class TodoTestFactory(BaseTestFactory):
    """Example factory for Todo items.

    Shows how to extend BaseTestFactory for specific models.
    """

    @classmethod
    def get_defaults(cls) -> dict[str, Any]:
        """Get default todo attributes."""
        gen = cls.generator
        return {
            "title": gen.title(words=random.randint(2, 5)),
            "description": gen.paragraph(sentences=2),
            "is_completed": random.choice([True, False]),
        }


class UserTestData:
    """Helper class for generating user test data.

    Provides common patterns for user-related tests.
    """

    def __init__(self):
        """Initialize with a data generator."""
        self.generator = TestDataGenerator()

    def signup_data(self, **overrides) -> dict[str, Any]:
        """Generate data for user signup.

        Args:
            **overrides: Override specific fields.

        Returns:
            dict: Signup data.
        """
        data = {
            "email": self.generator.email(),
            "password": self.generator.password(),
            "first_name": self.generator.first_name(),
            "last_name": self.generator.last_name(),
        }
        data.update(overrides)
        return data

    def login_data(
        self,
        email: str | None = None,
        password: str | None = None,
    ) -> dict[str, str]:
        """Generate data for user login.

        Args:
            email: Optional specific email.
            password: Optional specific password.

        Returns:
            dict: Login data.
        """
        return {
            "email": email or self.generator.email(),
            "password": password or self.generator.password(),
        }

    def profile_update_data(self, **overrides) -> dict[str, Any]:
        """Generate data for profile update.

        Args:
            **overrides: Override specific fields.

        Returns:
            dict: Profile update data.
        """
        data = {
            "first_name": self.generator.first_name(),
            "last_name": self.generator.last_name(),
            "bio": self.generator.sentence(words=10),
            "location": self.generator.city(),
        }
        data.update(overrides)
        return data
