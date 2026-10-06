"""Brute force protection via cache-backed attempt tracking.

Password logins (``/api/auth/login``, ``/api/auth/login/username``,
``/api/token/pair`` and the admin form) count failures per (account, client
IP) pair and per client IP. After ``MAX_ATTEMPTS`` failures for one account
from one IP, or ``IP_MAX_ATTEMPTS`` from one IP for any accounts, inside
``ATTEMPT_WINDOW``, that pair or IP gets 429 for ``LOCKOUT_SECONDS``, even
with the right password. No source can lock an account for everyone else:
the owner logging in from another IP is not affected. Unknown accounts lock
the same way, so a lockout reveals nothing about which accounts exist.
"""

import hashlib
import logging
from typing import Any

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from ninja_extra.exceptions import Throttled
from ninja_jwt.schema import TokenObtainPairInputSchema as BaseTokenObtainPairInput

from api.utils.http import get_client_ip

logger = logging.getLogger(__name__)

# Max failed attempts for one account from one client IP before lockout
MAX_ATTEMPTS = 5
# Max failed attempts per client IP, over all accounts, before lockout. Higher
# than the per-account limit because many users can share one NAT address.
IP_MAX_ATTEMPTS = 20
# Lockout duration in seconds (15 minutes)
LOCKOUT_SECONDS = 900
# Attempt window in seconds (5 minutes)
ATTEMPT_WINDOW = 300

LOCKOUT_MESSAGE = "Too many failed login attempts. Try again in 15 minutes."


def _key(identifier: str, prefix: str) -> str:
    hashed = hashlib.sha256(identifier.encode()).hexdigest()[:16]
    return f"bf:{prefix}:{hashed}"


def record_failed_attempt(identifier: str, max_attempts: int = MAX_ATTEMPTS) -> int:
    """Increment failure counter. Returns current attempt count."""
    attempts_key = _key(identifier, "attempts")
    # add + incr is atomic on Redis/Valkey, so parallel guesses each count.
    cache.add(attempts_key, 0, timeout=ATTEMPT_WINDOW)
    try:
        count = cache.incr(attempts_key)
    except ValueError:  # expired between add and incr
        cache.set(attempts_key, 1, timeout=ATTEMPT_WINDOW)
        count = 1

    if count >= max_attempts:
        lockout_key = _key(identifier, "lockout")
        cache.set(lockout_key, True, timeout=LOCKOUT_SECONDS)
        # The hashed key, not the identifier: logs must not carry emails.
        logger.warning("Locked out after %d failed attempts: %s", count, lockout_key)

    return count


def is_locked_out(identifier: str) -> bool:
    """Return True if this identifier is currently locked out."""
    return bool(cache.get(_key(identifier, "lockout")))


def clear_attempts(identifier: str) -> None:
    """Clear failure counters on successful authentication."""
    cache.delete(_key(identifier, "attempts"))
    cache.delete(_key(identifier, "lockout"))


def _login_keys(account: str, request: HttpRequest) -> tuple[str, str]:
    ip = get_client_ip(request)
    return f"login:{account}:ip:{ip}", f"login:ip:{ip}"


def is_login_locked(account: str, request: HttpRequest) -> bool:
    """Return True when ``account`` from this client IP, or the IP, is locked.

    ``account`` is namespaced by the caller, such as ``email:a@b.c``.
    """
    pair_key, ip_key = _login_keys(account, request)
    return is_locked_out(pair_key) or is_locked_out(ip_key)


def record_login_failure(account: str, request: HttpRequest) -> None:
    """Count one failed password login for ``account`` and the client IP."""
    pair_key, ip_key = _login_keys(account, request)
    record_failed_attempt(pair_key)
    record_failed_attempt(ip_key, max_attempts=IP_MAX_ATTEMPTS)


def clear_login_failures(account: str, request: HttpRequest) -> None:
    """Reset the (account, IP) counter after a successful login.

    The IP counter is left to expire, so one valid login cannot reset the
    budget of an address that is guessing other accounts.
    """
    clear_attempts(_login_keys(account, request)[0])


class TokenObtainPairInputSchema(BaseTokenObtainPairInput):
    """``/api/token/pair`` credentials with the shared login lockout.

    Uses the same ``email:`` account key as ``/api/auth/login``, so an
    attacker cannot switch endpoints to reset the count.
    """

    def authenticate(self, request: HttpRequest, credentials: dict[str, Any]) -> None:
        account = f"email:{str(credentials.get('email', '')).lower()}"
        if is_login_locked(account, request):
            raise Throttled(wait=LOCKOUT_SECONDS, detail=LOCKOUT_MESSAGE)
        try:
            super().authenticate(request, credentials)
        except Exception:
            record_login_failure(account, request)
            raise
        clear_login_failures(account, request)


def admin_login_with_lockout(request: HttpRequest, **kwargs: Any) -> HttpResponse:
    """Django admin login with the API login lockout.

    The admin form posts ``username`` (the email, ``USERNAME_FIELD``), so it
    shares the ``email:`` account key with ``/api/auth/login``. A failed POST
    re-renders the form with 200; a successful one redirects.
    """
    from django.contrib import admin

    if request.method != "POST":
        return admin.site.login(request, **kwargs)
    account = f"email:{request.POST.get('username', '').lower()}"
    if is_login_locked(account, request):
        return HttpResponse(LOCKOUT_MESSAGE, status=429, content_type="text/plain")
    response = admin.site.login(request, **kwargs)
    if response.status_code in (301, 302, 303):
        clear_login_failures(account, request)
    else:
        record_login_failure(account, request)
    return response
