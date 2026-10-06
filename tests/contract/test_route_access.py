"""Route access contract — consumes the public/protected endpoint fixtures.

Two concerns are covered here:

1. **Exhaustive classification** (``TestRouteClassificationExhaustiveness``):
   every registered API operation must be classified public or protected by
   the machine-readable fixtures in ``tests/contract/conftest.py``, with no
   unclassified route and no phantom classification. Docs/OpenAPI URLs live in
   an explicit ``route_exclusions`` fixture. This is the slice-1 deliverable.

2. **Anonymous-access smoke tests** (``TestRouteAccessContract``): a
   representative set of concrete routes that reach their handler when public,
   and reject anonymous requests when protected. These are deliberately
   representative, not exhaustive — the exhaustive set is asserted structurally
   by the classification test above.
"""

import json

import pytest
from django.test import Client

#: OpenAPI operations that count as routable methods.
_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

#: Concrete UUID used to materialize ``{user_id}``/``{audit_log_id}`` params.
_UUID = "00000000-0000-0000-0000-000000000000"


def _key(spec: dict) -> tuple[str, str]:
    """Normalize a ``{"method", "path"}`` spec to a ``(METHOD, path)`` tuple."""
    return (spec["method"].upper(), spec["path"])


def _spec_set(specs: list[dict]) -> set[tuple[str, str]]:
    """Convert a list of route specs to a normalized set."""
    return {_key(s) for s in specs}


def _openapi_ops(schema: dict) -> set[tuple[str, str]]:
    """Enumerate every routable operation in an OpenAPI schema."""
    ops: set[tuple[str, str]] = set()
    for path, methods in schema["paths"].items():
        for method in methods:
            if method in _HTTP_METHODS:
                ops.add((method.upper(), path))
    return ops


class TestRouteClassificationExhaustiveness:
    """The public/protected fixtures must classify every registered route."""

    @pytest.fixture(scope="class")
    def schema(self):
        from api.urls import api

        return api.get_openapi_schema()

    def test_every_route_is_classified_exactly_once(
        self,
        schema,
        public_endpoints,
        protected_endpoints,
        schema_hidden_endpoints,
    ):
        openapi_ops = _openapi_ops(schema)
        hidden = _spec_set(schema_hidden_endpoints)
        public = _spec_set(public_endpoints)
        protected = _spec_set(protected_endpoints)

        # Schema-hidden routes must genuinely be absent from the OpenAPI docs;
        # otherwise they should move into the schema-derived fixtures.
        assert not (hidden & openapi_ops), (
            f"schema-hidden routes leaked into OpenAPI: {sorted(hidden & openapi_ops)}"
        )

        # Schema-hidden routes are protected, not a third classification.
        assert hidden <= protected, (
            "schema-hidden routes must be a subset of protected: "
            f"{sorted(hidden - protected)}"
        )

        # Every registered route (OpenAPI + schema-hidden) must be classified
        # as public or protected, with no phantom classifications.
        registered = openapi_ops | hidden
        classified = public | protected
        unclassified = registered - classified
        phantom = classified - registered
        assert not unclassified, f"unclassified routes: {sorted(unclassified)}"
        assert not phantom, f"phantom routes: {sorted(phantom)}"

    def test_public_and_protected_are_disjoint(
        self, public_endpoints, protected_endpoints, schema_hidden_endpoints
    ):
        public = _spec_set(public_endpoints)
        protected = _spec_set(protected_endpoints)
        hidden = _spec_set(schema_hidden_endpoints)
        assert not (public & protected), (
            f"routes classified public and protected: {sorted(public & protected)}"
        )
        assert not (public & hidden), (
            f"routes classified public and schema-hidden: {sorted(public & hidden)}"
        )
        assert hidden <= protected, (
            f"schema-hidden routes must be a subset of protected: "
            f"{sorted(hidden - protected)}"
        )

    def test_exclusions_do_not_overlap_classified_routes(
        self,
        route_exclusions,
        public_endpoints,
        protected_endpoints,
        schema_hidden_endpoints,
    ):
        excluded = _spec_set(route_exclusions)
        classified = (
            _spec_set(public_endpoints)
            | _spec_set(protected_endpoints)
            | _spec_set(schema_hidden_endpoints)
        )
        overlap = excluded & classified
        assert not overlap, (
            f"docs/schema exclusions overlap classified routes: {sorted(overlap)}"
        )


@pytest.mark.django_db
class TestRouteAccessContract:
    """Anonymous access smoke tests on representative concrete routes."""

    @pytest.fixture
    def client(self):
        return Client()

    @staticmethod
    def _dispatch(client: Client, method: str, path: str, body: dict | None):
        if method == "GET":
            return client.get(path)
        if method == "DELETE":
            return client.delete(path)
        data = json.dumps(body if body is not None else {})
        return client.post(path, data=data, content_type="application/json")

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("GET", "/api/health/", None),
            ("GET", "/api/health/liveness", None),
            ("GET", "/api/health/readiness", None),
            ("POST", "/api/auth/login", {"email": "x@example.com"}),
            ("POST", "/api/auth/login/username", {"username": "x"}),
            ("POST", "/api/auth/signup", {"email": "x@example.com"}),
            (
                "POST",
                "/api/auth/passwordless/login/request",
                {"email": "x@example.com"},
            ),
            ("POST", "/api/auth/otp/request", {"email": "x@example.com"}),
            ("POST", "/api/token/pair", {}),
            ("POST", "/api/token/refresh", {}),
            ("POST", "/api/token/verify", {}),
        ],
    )
    def test_public_routes_reach_handler(self, client, method, path, body):
        response = self._dispatch(client, method, path, body)
        assert response.status_code != 401, (
            f"{method} {path} was wrongly protected: {response.status_code}"
        )

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("GET", "/api/auth/me", None),
            ("POST", "/api/auth/otp/2fa/request", {}),
            ("POST", "/api/auth/otp/2fa/verify", {"code": "123456"}),
            ("GET", "/api/users/", None),
            ("GET", "/api/api-keys/", None),
            ("GET", "/api/audit/", None),
            ("GET", "/api/tasks/stats", None),
            ("GET", "/api/tasks/scheduler/", None),
            ("GET", "/api/tasks/dlq/", None),
            ("GET", "/api/todos/", None),
            # Schema-hidden routes that still require authentication.
            ("GET", "/api/metrics", None),
            ("GET", "/api/events/stream/", None),
        ],
    )
    def test_protected_routes_reject_anonymous(self, client, method, path, body):
        response = self._dispatch(client, method, path, body)
        assert response.status_code == 401, f"{method} {path} -> {response.status_code}"


@pytest.mark.django_db
class TestRouteContractRegressions:
    """Regression coverage for the route-classification corrections.

    Guards two defects fixed alongside the exhaustive classification:

    - Static task POST routes (``/interval``, ``/crontab``, ``/retry-all``,
      ``/resolve-bulk``, ``/cleanup``) used to be shadowed by their sibling
      dynamic ``/{task_id}``/``/{entry_id}`` routes and returned 405 instead of
      rejecting anonymous requests with 401.
    - The 2FA OTP operations enforced auth manually but never declared
      ``JWTAuth``, so the OpenAPI schema listed them as public.
    """

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.mark.parametrize(
        "path",
        [
            "/api/tasks/scheduler/interval",
            "/api/tasks/scheduler/crontab",
            "/api/tasks/dlq/retry-all",
            "/api/tasks/dlq/resolve-bulk",
            "/api/tasks/dlq/cleanup",
        ],
    )
    def test_static_task_routes_not_shadowed(self, client, path):
        """Static POST routes reach auth instead of being 405-shadowed."""
        response = client.post(path, data="{}", content_type="application/json")
        assert response.status_code == 401, (
            f"{path} was shadowed by a dynamic route: {response.status_code}"
        )

    @pytest.mark.parametrize(
        "path",
        ["/api/auth/otp/2fa/request", "/api/auth/otp/2fa/verify"],
    )
    def test_two_factor_endpoints_reject_anonymous(self, client, path):
        """2FA operations enforce JWTAuth for anonymous requests."""
        response = client.post(path, data="{}", content_type="application/json")
        assert response.status_code == 401, f"{path} -> {response.status_code}"

    @pytest.mark.parametrize(
        "path",
        ["/api/auth/otp/2fa/request", "/api/auth/otp/2fa/verify"],
    )
    def test_two_factor_endpoints_declare_jwt_in_openapi(self, path):
        """2FA operations must declare bearer security in the OpenAPI schema."""
        from api.urls import api

        schema = api.get_openapi_schema()
        operation = schema["paths"][path]["post"]
        assert operation.get("security"), f"{path} missing OpenAPI security"


@pytest.mark.django_db
class TestSingleUnversionedApi:
    """The API is mounted exactly once, unversioned, at ``/api/``.

    Guards against reintroducing the inactive versioning mount: versioned
    ``/api/v1/`` and ``/api/v2/`` prefixes must resolve to 404, while the
    single unversioned API continues to serve its routes.
    """

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/health/",
            "/api/v1/token/pair",
            "/api/v1/users/",
            "/api/v2/health/",
            "/api/v2/token/pair",
            "/api/v2/users/",
        ],
    )
    def test_versioned_routes_not_mounted(self, client, path):
        """No versioned ``/api/v1/`` or ``/api/v2/`` prefix is mounted."""
        response = client.get(path)
        assert response.status_code == 404, (
            f"versioned route unexpectedly mounted: {path} -> {response.status_code}"
        )

    def test_unversioned_api_still_serves(self, client):
        """The single unversioned API continues to serve its routes."""
        response = client.get("/api/health/")
        assert response.status_code == 200, (
            f"unversioned API unreachable: /api/health/ -> {response.status_code}"
        )


_PASSWORD = "Pw-contract-123456"


@pytest.mark.django_db
class TestCookieCsrfContract:
    """The browser cookie + CSRF contract in ``docs/COOKIE_AUTH.md``.

    Unsafe ``/api/`` requests need ``X-CSRFToken`` unless they carry only
    header credentials. Login and refresh are not exempt.
    """

    @pytest.fixture
    def user(self, django_user_model):
        return django_user_model.objects.create_user(
            username="cookie", email="cookie@example.com", password=_PASSWORD
        )

    @pytest.fixture
    def browser(self):
        return Client(enforce_csrf_checks=True)

    @staticmethod
    def _post(client: Client, path: str, body: dict, **headers: str):
        return client.post(
            path, data=json.dumps(body), content_type="application/json", **headers
        )

    def _login(self, browser: Client) -> str:
        token = browser.get("/api/auth/csrf").json()["csrfToken"]
        response = self._post(
            browser,
            "/api/auth/login",
            {"email": "cookie@example.com", "password": _PASSWORD},
            HTTP_X_CSRFTOKEN=token,
        )
        assert response.status_code == 200, response.content
        return token

    def test_csrf_endpoint_sets_readable_cookie(self, browser):
        response = browser.get("/api/auth/csrf")
        assert response.status_code == 200
        cookie = response.cookies["csrftoken"]
        assert not cookie["httponly"]
        assert cookie["samesite"] == "Lax"
        assert response.json()["csrfToken"]

    def test_login_without_csrf_token_is_rejected(self, browser, user):
        browser.get("/api/auth/csrf")
        response = self._post(
            browser,
            "/api/auth/login",
            {"email": "cookie@example.com", "password": _PASSWORD},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "csrf_failed"

    def test_login_sets_httponly_auth_cookies(self, browser, user):
        self._login(browser)
        access = browser.cookies["access_token"]
        refresh = browser.cookies["refresh_token"]
        assert access["httponly"]
        assert refresh["httponly"]
        assert access["samesite"] == refresh["samesite"] == "Lax"
        assert refresh["path"] == "/api/auth/"
        assert browser.get("/api/auth/me").status_code == 200

    @pytest.mark.parametrize("headers", [{}, {"HTTP_AUTHORIZATION": "garbage"}])
    def test_cookie_requests_need_csrf_even_with_auth_header(
        self, browser, user, headers
    ):
        """A header must not let a cookie-carrying request skip CSRF."""
        self._login(browser)
        response = self._post(browser, "/api/auth/refresh", {}, **headers)
        assert response.status_code == 403
        assert response.json()["code"] == "csrf_failed"

    def test_refresh_rotates_cookies_and_revokes_old_token(self, browser, user):
        token = self._login(browser)
        old_refresh = browser.cookies["refresh_token"].value
        response = self._post(browser, "/api/auth/refresh", {}, HTTP_X_CSRFTOKEN=token)
        assert response.status_code == 200
        assert response.json() == {"access": None, "refresh": None}
        assert browser.cookies["refresh_token"].value != old_refresh

        replay = self._post(
            browser,
            "/api/auth/refresh",
            {"refresh": old_refresh},
            HTTP_X_CSRFTOKEN=token,
        )
        assert replay.status_code == 401

    def test_logout_after_access_cookie_expiry_revokes_refresh(self, browser, user):
        """The access cookie expires after an hour; logout must still revoke
        the 7-day refresh token and clear the cookies."""
        token = self._login(browser)
        old_refresh = browser.cookies["refresh_token"].value
        del browser.cookies["access_token"]
        response = self._post(browser, "/api/auth/logout", {}, HTTP_X_CSRFTOKEN=token)
        assert response.status_code == 200
        assert response.cookies["refresh_token"].value == ""
        replay = self._post(Client(), "/api/token/refresh", {"refresh": old_refresh})
        assert replay.status_code == 401

    def test_bearer_requests_without_cookies_skip_csrf(self, user):
        client = Client(enforce_csrf_checks=True)
        pair = self._post(
            client,
            "/api/token/pair",
            {"email": "cookie@example.com", "password": _PASSWORD},
        )
        assert pair.status_code == 200
        response = self._post(
            client,
            "/api/auth/logout",
            {"refresh": pair.json()["refresh"]},
            HTTP_AUTHORIZATION=f"Bearer {pair.json()['access']}",
        )
        assert response.status_code == 200
