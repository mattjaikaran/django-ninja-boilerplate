"""Ask a chat LLM the same typed questions, to measure what a decision costs.

The baseline sends one pack's questions and the state to any
OpenAI-compatible ``/v1/chat/completions`` endpoint and asks for a JSON object
of answers. Token counts come from the response's ``usage`` field, so they are
measured by the serving model, not estimated.

Configure ``DECISION_BASELINE_LLM_URL`` and ``DECISION_BASELINE_LLM_MODEL``
(and ``DECISION_BASELINE_LLM_API_KEY`` for a hosted API). A missing URL or an
unreachable endpoint fails loud.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

SYSTEM_PROMPT = (
    "You answer typed questions about a JSON state. For a 'choice' question, "
    "answer with exactly one option key. For a 'noul' question, answer true or "
    "false. Reply with one JSON object that maps each question key to its "
    "answer, and nothing else."
)

#: First JSON object in a reply, for models that wrap JSON in prose or fences.
JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True, slots=True)
class BaselineAnswer:
    """One baseline call: its answers (``None`` if unparsable) and usage."""

    answers: dict[str, Any] | None
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float

    @property
    def total_tokens(self) -> int:
        """Return prompt plus completion tokens."""
        return self.prompt_tokens + self.completion_tokens


def build_messages(
    state: dict[str, Any], questions: dict[str, Any]
) -> list[dict[str, str]]:
    """Return the chat messages for one typed-question request."""
    body = {"state": state, "questions": questions}
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(body, ensure_ascii=False)},
    ]


def parse_answers(content: str, questions: dict[str, Any]) -> dict[str, Any] | None:
    """Return valid answers from a reply, or ``None`` when any is invalid."""
    match = JSON_OBJECT.search(content or "")
    if not match:
        return None
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    answers: dict[str, Any] = {}
    for key, question in questions.items():
        value = raw.get(key)
        if question["type"] == "noul":
            if isinstance(value, str) and value.lower() in ("true", "false"):
                value = value.lower() == "true"
            if not isinstance(value, bool):
                return None
        elif value not in (question.get("criteria") or {}):
            return None
        answers[key] = value
    return answers


class BaselineLLM:
    """Client for the configured OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Read unset arguments from the ``DECISION_BASELINE_LLM_*`` settings."""
        self._client = client
        self.url = url if url is not None else settings.DECISION_BASELINE_LLM_URL
        self.model = (
            model if model is not None else settings.DECISION_BASELINE_LLM_MODEL
        )
        self._api_key = (
            api_key if api_key is not None else settings.DECISION_BASELINE_LLM_API_KEY
        )

    def ask(self, state: dict[str, Any], questions: dict[str, Any]) -> BaselineAnswer:
        """Ask the typed questions and return the answers and token usage.

        Raises:
            ImproperlyConfigured: If the URL is unset, the endpoint is
                unreachable or rejects the key, or the reply has no usage.
        """
        if not self.url:
            raise ImproperlyConfigured(
                "DECISION_BASELINE_LLM_URL is empty. Point it at an "
                "OpenAI-compatible /v1/chat/completions endpoint."
            )
        if self._client is None:
            self._client = httpx.Client(timeout=300.0)
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {
            "model": self.model,
            "messages": build_messages(state, questions),
            "temperature": 0,
        }
        started = time.perf_counter()
        try:
            response = self._client.post(self.url, json=payload, headers=headers)
        except httpx.TransportError as exc:
            raise ImproperlyConfigured(
                f"The baseline LLM is unreachable at {self.url}: {exc}"
            ) from exc
        latency = (time.perf_counter() - started) * 1000
        if response.status_code in (401, 403):
            raise ImproperlyConfigured(
                f"The baseline LLM rejected the request with {response.status_code}. "
                "Check DECISION_BASELINE_LLM_API_KEY."
            )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage") or {}
        if "prompt_tokens" not in usage:
            raise ImproperlyConfigured(
                "The baseline LLM response has no usage.prompt_tokens, so tokens "
                "cannot be measured."
            )
        content = data["choices"][0]["message"].get("content") or ""
        return BaselineAnswer(
            answers=parse_answers(content, questions),
            prompt_tokens=int(usage["prompt_tokens"]),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            latency_ms=latency,
        )
