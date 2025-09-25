import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from faker import Faker

User = get_user_model()
fake = Faker()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for creating User instances."""

    class Meta:
        model = User

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    email = factory.LazyAttribute(
        lambda obj: f"{obj.first_name.lower()}.{obj.last_name.lower()}@example.com"
    )
    username = factory.LazyAttribute(
        lambda obj: f"{obj.first_name.lower()}{obj.last_name.lower()}{fake.random_int(100, 999)}"
    )
    password = factory.LazyFunction(lambda: make_password("testpass123"))
    is_staff = False
    is_superuser = False

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
    """Factory for creating admin User instances."""

    is_staff = True
    is_superuser = False


class SuperUserFactory(UserFactory):
    """Factory for creating superuser User instances."""

    is_staff = True
    is_superuser = True
