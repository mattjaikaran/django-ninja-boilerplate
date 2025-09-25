import factory

from core.tests.factories import UserFactory
from todos.models import Todo


class TodoFactory(factory.django.DjangoModelFactory):
    """Factory for creating Todo instances."""

    class Meta:
        model = Todo

    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("text", max_nb_chars=200)
    is_completed = False
    created_by = factory.SubFactory(UserFactory)
    updated_by = factory.SelfAttribute("created_by")
