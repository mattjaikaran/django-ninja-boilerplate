"""Tests for the observability admin pages.

The health and metrics pages render inside the Unfold admin and are
staff-only, mirroring the atlas admin views. Health checks run against
the real database and cache; no database mocking.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


class TestHealthAdminPage:
    """Integration tests for the health check admin page."""

    def test_requires_staff_redirect(self, api_client):
        response = api_client.get("/admin/observability/health/")
        assert response.status_code in (301, 302)

    def test_staff_can_view_page(self, api_client, staff_user):
        api_client.force_login(staff_user)
        response = api_client.get("/admin/observability/health/")
        assert b"Health Check" in response.content
        assert b"database" in response.content
        assert b"cache" in response.content
        assert b"celery" in response.content


class TestMetricsAdminPage:
    """Integration tests for the metrics admin page."""

    def test_requires_staff_redirect(self, api_client):
        response = api_client.get("/admin/observability/metrics/")
        assert response.status_code in (301, 302)

    def test_staff_can_view_page(self, api_client, staff_user):
        api_client.force_login(staff_user)
        response = api_client.get("/admin/observability/metrics/")
        assert response.status_code == 200
        assert b"API Metrics" in response.content
        assert b"http_requests_total" in response.content
        assert b"db_query_duration_seconds" in response.content
