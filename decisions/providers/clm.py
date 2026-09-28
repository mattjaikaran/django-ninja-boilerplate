"""Provider for the open-source CLM System One HTTP service."""

from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from decisions.providers.base import DecisionProvider, DecisionResult, result_from_raw


class ClmProvider(DecisionProvider):
    """Ask a separately hosted CLM encoder to answer typed questions."""

    name = "clm"

    def __init__(
        self,
        client: httpx.Client | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._client = client
        self._base_url = (
            base_url if base_url is not None else settings.CLM_BASE_URL
        ).rstrip("/")
        self._api_key = api_key if api_key is not None else settings.CLM_API_KEY

    def is_available(self) -> bool:
        """Return whether a CLM endpoint is configured, not whether it is healthy."""
        return bool(self._base_url)

    def predict(
        self,
        state: dict[str, Any],
        questions: dict[str, Any],
    ) -> DecisionResult:
        """Call the CLM wire API without changing the selected provider."""
        if not self._base_url:
            raise ImproperlyConfigured(
                "CLM_BASE_URL is empty. Start the decisions-clm profile on a "
                "GPU host or configure an existing CLM endpoint."
            )
        if self._client is None:
            self._client = httpx.Client(timeout=120.0)
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            response = self._client.post(
                f"{self._base_url}/v1/systemone",
                json={"state": state, "questions": questions},
                headers=headers,
            )
        except httpx.ConnectError as exc:
            raise ImproperlyConfigured(
                f"CLM is unreachable at {self._base_url}. Start the decisions-clm "
                "profile on a GPU host or fix CLM_BASE_URL / CLM_CONTAINER_URL."
            ) from exc
        if response.status_code in (401, 403):
            raise ImproperlyConfigured(
                f"CLM rejected the request with {response.status_code}. Set the "
                "same CLM_API_KEY for Django and the clm-api service."
            )
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict) or not isinstance(raw.get("answers"), dict):
            raise TypeError("CLM response has no answers mapping")
        if raw["answers"].keys() != questions.keys():
            raise ValueError("CLM response omitted or added question answers")
        return result_from_raw(raw, self.name)
