"""Laya provider — the in-process System 1 decision engine.

Laya is the default provider. It runs in-process: the router is created once
and reused across requests, and it keeps checkpoints resident.

Laya ships with heavy dependencies (``torch``, ``transformers``), so it is an
optional extra. When the package is missing this provider **fails loud** with
an :class:`~django.core.exceptions.ImproperlyConfigured` error that explains
how to install it. It never silently falls back to another provider.

Laya's engine class is imported as ``LayaEngine`` so the convention checker's
third-party-router rule does not mistake it for a function-based view.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from decisions.providers.base import DecisionProvider, DecisionResult, result_from_raw

logger = logging.getLogger(__name__)

#: Message shown when the optional Laya extra is not installed.
INSTALL_HINT = (
    "The 'laya' package is not installed, so the Laya provider cannot run. "
    "Install the decisions-laya extra with `uv sync --extra decisions-laya`, "
    "or set SYSTEMONE_PROVIDER to a provider that is available."
)


def _laya_installed() -> bool:
    """Return ``True`` when the ``laya`` package can be imported."""
    try:
        return importlib.util.find_spec("laya") is not None
    except (ImportError, ValueError):
        return False


class LayaProvider(DecisionProvider):
    """Decision provider backed by the in-process Laya router."""

    name = "laya"

    def __init__(self, router: Any = None, preload: bool = False) -> None:
        """Initialise the provider.

        Args:
            router: Pre-built Laya router. Pass one to skip package loading,
                which tests use to exercise the response mapping.
            preload: Load every configured checkpoint when the router is
                built. Production should set this to remove first-request
                latency; the default keeps development fast and offline.
        """
        self._router = router
        self._preload = preload

    def is_available(self) -> bool:
        """Return ``True`` when a router is set or the package is installed."""
        return self._router is not None or _laya_installed()

    def _get_router(self) -> Any:
        """Return the Laya router, loading it on first use.

        Returns:
            The Laya router instance.

        Raises:
            ImproperlyConfigured: If the ``laya`` package is not installed.
        """
        if self._router is not None:
            return self._router
        try:
            from laya import Router as LayaEngine  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImproperlyConfigured(INSTALL_HINT) from exc
        self._router = LayaEngine(preload=self._preload)
        return self._router

    def predict(
        self,
        state: dict[str, Any],
        questions: dict[str, Any],
    ) -> DecisionResult:
        """Answer *questions* using the Laya router.

        Laya returns per-answer confidence and routing metadata, which
        :func:`result_from_raw` normalises and reduces to one confidence.

        Args:
            state: Structured input for the decision.
            questions: Mapping of question key to a question definition.

        Returns:
            The Laya result normalised to a :class:`DecisionResult`.

        Raises:
            ImproperlyConfigured: If the ``laya`` package is not installed.
        """
        raw = self._get_router().predict(state, questions)
        return result_from_raw(raw, self.name)
