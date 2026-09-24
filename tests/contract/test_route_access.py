"""Route access contract — consumes the public/protected endpoint fixtures.

These tests drive the machine-readable ``public_endpoints`` and
``protected_endpoints`` fixtures from ``tests/contract/conftest.py`` against
the in-process Django test client, asserting the anonymous-access contract:

- Public routes (deployment probes, auth operations, token issuance) must
  reach their handler — never a 401.
- Protected routes (observability detail/metrics, session, administration,
  task internals, audit, decisions, todos) must reject anonymous requests
  with 401.
"""

import pytest
from django.test import Client


def _call(client: Client, spec: dict):
    """Dispatch a route spec to the test client."""
    method = spec["method"]
    path = spec["path"]
    if method == "GET":
        return client.get(path)
    if method == "POST":
        return client.post(path, data="{}", content_type="application/json")
    raise ValueError(f"Unsupported method {method!r}")


@pytest.mark.django_db
class TestRouteAccessContract:
    """Anonymous access assertions driven by the route fixtures."""

    @pytest.fixture
    def client(self):
        return Client()

    def test_public_endpoints_reach_handler(self, client, public_endpoints):
        for spec in public_endpoints:
            response = _call(client, spec)
            assert response.status_code != 401, (
                f"{spec['method']} {spec['path']} was wrongly protected: "
                f"{response.status_code}"
            )

    def test_protected_endpoints_reject_anonymous(self, client, protected_endpoints):
        for spec in protected_endpoints:
            response = _call(client, spec)
            assert response.status_code == 401, (
                f"{spec['method']} {spec['path']} -> {response.status_code}"
            )
