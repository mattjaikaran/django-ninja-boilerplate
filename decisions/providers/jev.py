"""Jev (TypeSafe) provider — the hosted decision API.

Jev is optional. It needs ``TYPESAFE_API_KEY`` in the environment and the
``typesafe-sdk`` extra. When either is missing the provider **fails loud**
with an :class:`~django.core.exceptions.ImproperlyConfigured` error rather
than answering with a partial result.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from decisions.providers.base import DecisionProvider, DecisionResult, result_from_raw

logger = logging.getLogger(__name__)

#: Message shown when ``TYPESAFE_API_KEY`` is not set.
MISSING_KEY_HINT = (
    "TYPESAFE_API_KEY is not set, so the Jev provider cannot run. Set it in "
    "your environment, or set SYSTEMONE_PROVIDER to a provider that is "
    "available."
)

#: Message shown when the optional TypeSafe extra is not installed.
INSTALL_HINT = (
    "The 'typesafe-sdk' package is not installed, so the Jev provider cannot "
    "run. Install the decisions-jev extra with "
    "`uv sync --extra decisions-jev`."
)


def _sdk_installed() -> bool:
    """Return ``True`` when the ``typesafe_sdk`` package can be imported."""
    try:
        return importlib.util.find_spec("typesafe_sdk") is not None
    except (ImportError, ValueError):
        return False


class JevProvider(DecisionProvider):
    """Decision provider backed by the hosted TypeSafe API."""

    name = "jev"

    def __init__(self, client: Any = None, api_key: str | None = None) -> None:
        """Initialise the provider.

        Args:
            client: Pre-built TypeSafe client. Pass one to skip package
                loading, which tests use to exercise the response mapping.
            api_key: API key override. Defaults to ``settings.TYPESAFE_API_KEY``.
        """
        self._client = client
        self._api_key = (
            api_key
            if api_key is not None
            else getattr(settings, "TYPESAFE_API_KEY", "")
        )

    def is_available(self) -> bool:
        """Return ``True`` when a key is set and a client can be built."""
        if not self._api_key:
            return False
        return self._client is not None or _sdk_installed()

    def _get_client(self) -> Any:
        """Return the TypeSafe client, building it on first use.

        Returns:
            The TypeSafe client instance.

        Raises:
            ImproperlyConfigured: If the API key or the package is missing.
        """
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise ImproperlyConfigured(MISSING_KEY_HINT)
        try:
            from typesafe_sdk import Client  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImproperlyConfigured(INSTALL_HINT) from exc
        self._client = Client(api_key=self._api_key)
        return self._client

    def predict(
        self,
        state: dict[str, Any],
        questions: dict[str, Any],
    ) -> DecisionResult:
        """Answer *questions* using the TypeSafe API.

        Args:
            state: Structured input for the decision.
            questions: Mapping of question key to a question definition.

        Returns:
            The TypeSafe result normalised to a :class:`DecisionResult`. The
            Jev-compatible API returns the same per-answer ``confidence`` and
            ``routing`` shape as Laya, so both share one normaliser.

        Raises:
            ImproperlyConfigured: If the API key or package is missing.
        """
        raw = self._get_client().decide(state=state, questions=questions)
        return result_from_raw(raw, self.name)
