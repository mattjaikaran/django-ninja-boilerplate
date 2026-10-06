"""Provider-neutral LLM and embedding client.

It speaks the OpenAI-compatible HTTP API (``/chat/completions``,
``/embeddings``), which OpenAI, Ollama, vLLM, LM Studio, OpenRouter and a
LiteLLM proxy all serve. It uses httpx, a core dependency, so it adds no SDK.
Configure it with the ``AI_*`` settings; keys come only from the environment.

Each request opens an OpenTelemetry span that follows the GenAI semantic
conventions (``gen_ai.*`` attributes, span name ``"{operation} {model}"``,
kind CLIENT). Without the `observability` extra the spans are no-ops.

Chat responses are cached in the default cache (Valkey) under a hash of the
model, messages and sampling parameters for ``AI_CACHE_TTL`` seconds.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import urlsplit

import httpx
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

from core.observability.tracing import get_tracer

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import TracebackType

# Bump the version when ChatResult changes shape, so old entries miss.
CACHE_KEY_PREFIX = "ai:chat:v1:"

Message = dict[str, str]


def prompt_cache_key(
    model: str, messages: list[Message], **params: float | None
) -> str:
    """Return the cache key for one chat request.

    The key is a SHA-256 of the model, the messages and the sampling
    parameters, so any change to them is a different entry. Dict key order
    does not change the key.
    """
    payload = json.dumps(
        {"model": model, "messages": messages, "params": params},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return CACHE_KEY_PREFIX + hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str
    finish_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    cached: bool = False


class AIClient:
    """Client for one OpenAI-compatible endpoint. Use it as a context manager."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        provider_name: str,
        timeout: float,
        cache_ttl: int,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not base_url:
            raise ImproperlyConfigured(
                "AI_BASE_URL is empty. Set it to an OpenAI-compatible API, for "
                "example https://api.openai.com/v1 or http://localhost:11434/v1."
            )
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.provider_name = provider_name
        self.cache_ttl = cache_ttl
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers=headers,
            timeout=timeout,
            transport=transport,
        )
        url = urlsplit(base_url)
        self._server = {
            "server.address": url.hostname or "",
            "server.port": url.port or (443 if url.scheme == "https" else 80),
        }

    @classmethod
    def from_settings(cls) -> AIClient:
        return cls(
            base_url=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
            chat_model=settings.AI_CHAT_MODEL,
            embedding_model=settings.AI_EMBEDDING_MODEL,
            provider_name=settings.AI_PROVIDER_NAME,
            timeout=settings.AI_TIMEOUT,
            cache_ttl=settings.AI_CACHE_TTL,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_cache: bool = True,
    ) -> ChatResult:
        """Send a chat completion. A cache hit makes no request and no span."""
        model = self._require_model(model or self.chat_model, "AI_CHAT_MODEL")
        params = {"temperature": temperature, "max_tokens": max_tokens}
        key = prompt_cache_key(model, messages, **params)
        caching = use_cache and self.cache_ttl > 0
        if caching and (hit := cache.get(key)) is not None:
            return ChatResult(**{**hit, "cached": True})

        request_attributes = {
            "gen_ai.request.temperature": temperature,
            "gen_ai.request.max_tokens": max_tokens,
        }
        with self._span("chat", model, request_attributes) as span:
            body: dict[str, Any] = {"model": model, "messages": messages}
            body.update({k: v for k, v in params.items() if v is not None})
            data = self._post("chat/completions", body)
            choice = data["choices"][0]
            usage = data.get("usage") or {}
            result = ChatResult(
                content=choice["message"]["content"],
                model=data.get("model") or model,
                finish_reason=choice.get("finish_reason"),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
            _set_attributes(
                span,
                {
                    "gen_ai.response.id": data.get("id"),
                    "gen_ai.response.model": result.model,
                    "gen_ai.response.finish_reasons": (
                        [result.finish_reason] if result.finish_reason else None
                    ),
                    "gen_ai.usage.input_tokens": result.input_tokens,
                    "gen_ai.usage.output_tokens": result.output_tokens,
                },
            )
        if caching:
            cache.set(key, asdict(result), self.cache_ttl)
        return result

    def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        """Return one embedding per text, in input order."""
        model = self._require_model(model or self.embedding_model, "AI_EMBEDDING_MODEL")
        with self._span("embeddings", model) as span:
            data = self._post("embeddings", {"model": model, "input": texts})
            items = sorted(data["data"], key=lambda item: item["index"])
            usage = data.get("usage") or {}
            _set_attributes(
                span,
                {
                    "gen_ai.response.model": data.get("model"),
                    "gen_ai.usage.input_tokens": usage.get("prompt_tokens"),
                },
            )
        return [item["embedding"] for item in items]

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self._http.post(path, json=body)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _require_model(model: str, setting: str) -> str:
        if not model:
            raise ImproperlyConfigured(f"{setting} is empty and no model was passed.")
        return model

    @contextmanager
    def _span(
        self, operation: str, model: str, extra: dict[str, Any] | None = None
    ) -> Iterator[Any]:
        attributes = {
            "gen_ai.operation.name": operation,
            "gen_ai.provider.name": self.provider_name,
            "gen_ai.request.model": model,
            **self._server,
            **(extra or {}),
        }
        options: dict[str, Any] = {
            "attributes": {k: v for k, v in attributes.items() if v is not None}
        }
        try:
            from opentelemetry.trace import SpanKind

            options["kind"] = SpanKind.CLIENT
        except ImportError:
            pass
        name = f"{operation} {model}"
        with get_tracer().start_as_current_span(name, **options) as span:
            try:
                yield span
            except Exception as exc:
                span.set_attribute("error.type", type(exc).__qualname__)
                raise


def _set_attributes(span: Any, attributes: dict[str, Any]) -> None:
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)
