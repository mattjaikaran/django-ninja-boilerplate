from datetime import datetime, timedelta

import factory

from core.models import OneTimePassword

from .user_factory import UserFactory


class OneTimePasswordFactory(factory.django.DjangoModelFactory):
    """Factory for creating OneTimePassword instances."""

    class Meta:
        model = OneTimePassword

    user = factory.SubFactory(UserFactory)
    token = factory.Faker("uuid4")
    expires_at = factory.LazyFunction(lambda: datetime.now() + timedelta(minutes=15))
    is_used = False
