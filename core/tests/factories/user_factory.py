"""User factories for testing.

This module provides Factory Boy factories for creating User instances
in tests without needing database fixtures or mocks.
"""

import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from faker import Faker

User = get_user_model()
fake = Faker()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances.

    Usage:
        user = UserFactory()  # Regular user
        user = UserFactory(is_verified=True)  # Verified user
        user = UserFactory(first_name="John")  # Custom fields
    """

    class Meta:
        model = User
        skip_postgeneration_save = True

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    email = factory.LazyAttribute(
        lambda obj: (
            f"{obj.first_name.lower()}.{obj.last_name.lower()}.{fake.random_int(100, 999)}@example.com"
        )
    )
    username = factory.LazyAttribute(
        lambda obj: (
            f"{obj.first_name.lower()}{obj.last_name.lower()}{fake.random_int(100, 999)}"
        )
    )
    password = factory.LazyFunction(lambda: make_password("testpass123"))

    # Profile fields
    bio = factory.Faker("sentence", nb_words=10)
    phone = factory.LazyFunction(lambda: f"+1{fake.random_int(1000000000, 9999999999)}")
    location = factory.Faker("city")
    website = factory.LazyAttribute(lambda obj: f"https://{obj.username}.example.com")
    timezone = "UTC"

    # Status fields
    is_active = True
    is_staff = False
    is_superuser = False
    is_verified = False

    # Preferences
    email_notifications = True
    push_notifications = True

    @factory.post_generation
    def set_password(self, create, extracted, **_kwargs):
        """Set password after creation."""
        if not create:
            return
        if extracted:
            self.set_password(extracted)
        else:
            self.set_password("testpass123")
        self.save()


class AdminUserFactory(UserFactory):
    """Factory for creating admin (staff) User instances."""

    is_staff = True
    is_superuser = False


class SuperUserFactory(UserFactory):
    """Factory for creating superuser instances."""

    is_staff = True
    is_superuser = True
    is_verified = True


class VerifiedUserFactory(UserFactory):
    """Factory for creating verified User instances."""

    is_verified = True


class InactiveUserFactory(UserFactory):
    """Factory for creating inactive User instances."""

    is_active = False
