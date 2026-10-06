"""SSRF guard for outbound webhook requests.

``validate_webhook_url`` resolves the host once and rejects the URL if any
resolved address is not public. ``post_webhook`` then connects to that vetted
address. The request keeps the original Host header and TLS SNI, so the
certificate check still uses the hostname, and a DNS rebind between the check
and the connection cannot change the target.
"""

import ipaddress
import socket
from dataclasses import dataclass

import httpx
from django.conf import settings

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

# Seconds. Short, so a slow receiver cannot hold a worker.
CONNECT_TIMEOUT = 5.0
REQUEST_TIMEOUT = 10.0
# Bytes of the response body that delivery reads and stores.
MAX_RESPONSE_BYTES = 64 * 1024

_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")


class UnsafeWebhookURLError(ValueError):
    """The webhook URL uses a blocked scheme or resolves to a blocked address."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        # True only for DNS failures, which can be transient.
        self.retryable = retryable


@dataclass(frozen=True)
class VettedURL:
    url: httpx.URL
    host: str
    ip: IPAddress


@dataclass(frozen=True)
class WebhookResponse:
    status_code: int
    body: str


def _embedded_ipv4(ip: IPAddress) -> ipaddress.IPv4Address | None:
    """Return the IPv4 address that an IPv6 transition address carries."""
    if not isinstance(ip, ipaddress.IPv6Address):
        return None
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip.teredo is not None:
        return ip.teredo[1]
    if ip in _NAT64_PREFIX:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def is_public_ip(ip: IPAddress) -> bool:
    """Return True only for globally routable unicast addresses."""
    candidates: list[IPAddress] = [ip]
    embedded = _embedded_ipv4(ip)
    if embedded is not None:
        candidates.append(embedded)
    return not any(
        not addr.is_global
        or addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        for addr in candidates
    )


def _allowed_schemes() -> set[str]:
    if settings.DEBUG or getattr(settings, "WEBHOOKS_ALLOW_HTTP", False):
        return {"https", "http"}
    return {"https"}


def validate_webhook_url(url: str) -> VettedURL:
    """Check the scheme, resolve the host once, and reject non-public targets.

    Raises:
        UnsafeWebhookURLError: The URL is not safe to call.
    """
    try:
        parsed = httpx.URL(url)
    except (httpx.InvalidURL, TypeError) as exc:
        raise UnsafeWebhookURLError("Webhook URL is not valid.") from exc

    if parsed.scheme not in _allowed_schemes():
        raise UnsafeWebhookURLError("Webhook URL must use https.")
    if parsed.userinfo:
        raise UnsafeWebhookURLError("Webhook URL must not contain credentials.")
    host = parsed.raw_host.decode("ascii")
    if not host:
        raise UnsafeWebhookURLError("Webhook URL has no host.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as exc:
        raise UnsafeWebhookURLError(
            "Webhook host does not resolve.", retryable=True
        ) from exc

    addresses: list[IPAddress] = []
    for info in infos:
        # Drop an IPv6 zone ID ("fe80::1%en0"); zoned addresses are link-local.
        ip = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        if not is_public_ip(ip):
            raise UnsafeWebhookURLError(
                "Webhook host resolves to a non-public address."
            )
        addresses.append(ip)
    if not addresses:
        raise UnsafeWebhookURLError("Webhook host does not resolve.", retryable=True)
    return VettedURL(url=parsed, host=host, ip=addresses[0])


def post_webhook(
    url: str,
    content: bytes,
    headers: dict[str, str],
    *,
    transport: httpx.BaseTransport | None = None,
) -> WebhookResponse:
    """POST to a vetted webhook URL, pinned to the address checked above.

    The client does not follow redirects, ignores proxy environment variables,
    and reads at most ``MAX_RESPONSE_BYTES`` of the response body.
    """
    vetted = validate_webhook_url(url)
    request_headers = httpx.Headers(headers)
    # Set after the user headers so a stored "Host" header cannot override it.
    request_headers["Host"] = vetted.url.netloc.decode("ascii")
    # Raw bytes only: a compressed body could expand past the read limit.
    request_headers["Accept-Encoding"] = "identity"

    with (
        httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT),
            follow_redirects=False,
            trust_env=False,
        ) as client,
        client.stream(
            "POST",
            vetted.url.copy_with(host=str(vetted.ip)),
            content=content,
            headers=request_headers,
            extensions={"sni_hostname": vetted.host},
        ) as response,
    ):
        body = bytearray()
        for chunk in response.iter_raw():
            body += chunk[: MAX_RESPONSE_BYTES - len(body)]
            if len(body) >= MAX_RESPONSE_BYTES:
                break
    return WebhookResponse(
        status_code=response.status_code,
        body=body.decode("utf-8", errors="replace"),
    )
