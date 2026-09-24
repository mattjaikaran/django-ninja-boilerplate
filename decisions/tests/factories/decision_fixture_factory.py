import factory

from decisions.models import DecisionFixture


class DecisionFixtureFactory(factory.django.DjangoModelFactory):
    """Factory for creating DecisionFixture instances."""

    class Meta:
        model = DecisionFixture

    kind = "support_ticket"
    name = factory.Sequence(lambda n: f"fixture-{n}")
    description = factory.Faker("sentence")
    payload = factory.LazyFunction(lambda: {"ticket_id": "T-1"})
    embedding = None
