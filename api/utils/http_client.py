"""Reusable HTTP client built on httpx with Pydantic response parsing.

Usage:
    from api.utils.http_client import http_client

    # Simple GET
    data = await http_client.get("https://api.example.com/users")

    # GET with Pydantic parsing
    users = await http_client.get("https://api.example.com/users", response_model=list[UserSchema])

    # POST with JSON body
    user = await http_client.post(
        "https://api.example.com/users",
        json={"name": "Matt"},
        response_model=UserSchema,
        expected_status=201,
    )

    # Sync usage
    data = http_client.sync_get("https://api.example.com/health")
"""

import logging
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class HttpClientError(Exception):
    """Raised when an HTTP request fails."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class HttpClient:
    """Async/sync HTTP client with Pydantic response parsing and structured error handling.

    Features:
        - Async-first with sync convenience methods
        - Automatic Pydantic model parsing via response_model
        - Expected status code validation
        - Configurable timeouts and retries
        - Structured logging on failures
    """

    def __init__(
        self,
        base_url: str = "",
        timeout: float = 30.0,
        max_retries: int = 0,
        default_headers: dict[str, str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.default_headers = default_headers or {}

    def _build_url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _merge_headers(self, headers: dict[str, str] | None) -> dict[str, str]:
        merged = {**self.default_headers}
        if headers:
            merged.update(headers)
        return merged

    def _validate_status(
        self,
        response: httpx.Response,
        expected_status: int | list[int] | None,
    ) -> None:
        if expected_status is None:
            response.raise_for_status()
            return

        expected = (
            [expected_status] if isinstance(expected_status, int) else expected_status
        )
        if response.status_code not in expected:
            raise HttpClientError(
                f"Expected status {expected}, got {response.status_code}",
                status_code=response.status_code,
                response_body=response.text,
            )

    def _parse_response(
        self,
        response: httpx.Response,
        response_model: type | None,
    ) -> Any:
        data = response.json()
        if response_model is None:
            return data
        adapter = TypeAdapter(response_model)
        return adapter.validate_python(data)

    # ── Async methods ──────────────────────────────────────────────

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
        files: Any = None,
        timeout: float | None = None,
        expected_status: int | list[int] | None = None,
        response_model: type | None = None,
        max_retries: int | None = None,
    ) -> Any:
        url = self._build_url(path)
        merged_headers = self._merge_headers(headers)
        retries = max_retries if max_retries is not None else self.max_retries
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method,
                        url,
                        json=json,
                        params=params,
                        headers=merged_headers,
                        data=data,
                        files=files,
                        timeout=timeout or self.timeout,
                    )
                self._validate_status(response, expected_status)
                return self._parse_response(response, response_model)
            except (httpx.HTTPError, HttpClientError) as e:
                last_error = e
                if attempt < retries:
                    logger.warning(
                        "HTTP %s %s attempt %d failed: %s",
                        method,
                        url,
                        attempt + 1,
                        e,
                    )
                    continue
                logger.error(
                    "HTTP %s %s failed after %d attempts: %s",
                    method,
                    url,
                    attempt + 1,
                    e,
                )
                raise

        raise last_error  # type: ignore[misc]

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PUT", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any:
        return await self.request("DELETE", path, **kwargs)

    # ── Sync methods ───────────────────────────────────────────────

    def sync_request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
        files: Any = None,
        timeout: float | None = None,
        expected_status: int | list[int] | None = None,
        response_model: type | None = None,
        max_retries: int | None = None,
    ) -> Any:
        url = self._build_url(path)
        merged_headers = self._merge_headers(headers)
        retries = max_retries if max_retries is not None else self.max_retries
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                response = httpx.request(
                    method,
                    url,
                    json=json,
                    params=params,
                    headers=merged_headers,
                    data=data,
                    files=files,
                    timeout=timeout or self.timeout,
                )
                self._validate_status(response, expected_status)
                return self._parse_response(response, response_model)
            except (httpx.HTTPError, HttpClientError) as e:
                last_error = e
                if attempt < retries:
                    logger.warning(
                        "HTTP %s %s attempt %d failed: %s",
                        method,
                        url,
                        attempt + 1,
                        e,
                    )
                    continue
                logger.error(
                    "HTTP %s %s failed after %d attempts: %s",
                    method,
                    url,
                    attempt + 1,
                    e,
                )
                raise

        raise last_error  # type: ignore[misc]

    def sync_get(self, path: str, **kwargs: Any) -> Any:
        return self.sync_request("GET", path, **kwargs)

    def sync_post(self, path: str, **kwargs: Any) -> Any:
        return self.sync_request("POST", path, **kwargs)

    def sync_put(self, path: str, **kwargs: Any) -> Any:
        return self.sync_request("PUT", path, **kwargs)

    def sync_patch(self, path: str, **kwargs: Any) -> Any:
        return self.sync_request("PATCH", path, **kwargs)

    def sync_delete(self, path: str, **kwargs: Any) -> Any:
        return self.sync_request("DELETE", path, **kwargs)


# Module-level default client — import and use directly.
http_client = HttpClient()
