"""Decision providers.

This package exposes the provider interface, the concrete providers, and the
registry that maps a provider name to its class. Add a provider by writing a
:class:`~decisions.providers.base.DecisionProvider` subclass and registering
it in :data:`PROVIDER_REGISTRY`.
"""

from decisions.providers.base import (
    ANSWER_VALUE_KEYS,
    DecisionProvider,
    DecisionResult,
    aggregate_confidence,
    result_from_raw,
)
from decisions.providers.fake import FakeProvider
from decisions.providers.jev import JevProvider
from decisions.providers.laya import LayaProvider

#: Maps a provider name to its class. The key is the name used in settings
#: (``SYSTEMONE_PROVIDER``) and in the ``provider`` request field.
PROVIDER_REGISTRY: dict[str, type[DecisionProvider]] = {
    FakeProvider.name: FakeProvider,
    LayaProvider.name: LayaProvider,
    JevProvider.name: JevProvider,
}


def available_providers() -> list[str]:
    """Return the sorted names of every registered provider.

    Returns:
        Provider names in alphabetical order.
    """
    return sorted(PROVIDER_REGISTRY)


__all__ = [
    "ANSWER_VALUE_KEYS",
    "PROVIDER_REGISTRY",
    "DecisionProvider",
    "DecisionResult",
    "FakeProvider",
    "JevProvider",
    "LayaProvider",
    "aggregate_confidence",
    "available_providers",
    "result_from_raw",
]
