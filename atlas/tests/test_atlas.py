"""Tests for the codebase atlas generator and admin views.

The generator scans the real project (apps, LOC, OpenAPI routes) and the
admin views are exercised through the Django test client with a staff
user. No database mocking: the generator reads the real schema and the
real audit log.
"""

from __future__ import annotations

import json

import pytest

from atlas.services.atlas_service import generate_atlas

pytestmark = pytest.mark.django_db


class TestAtlasGenerator:
    """Unit tests for the atlas data generator."""

    def test_generates_expected_structure(self):
        data = generate_atlas(include_real_samples=False)
        assert data["meta"]["app_count"] >= 3
        assert data["meta"]["total_loc"] > 0
        ids = {structure["id"] for structure in data["structures"]}
        assert "api" in ids
        assert "core" in ids
        assert "todos" in ids
        assert any(
            edge["f"] == "client" and edge["t"] == "api" for edge in data["edges"]
        )
        assert data["trace"]

    def test_every_edge_references_existing_nodes(self):
        data = generate_atlas(include_real_samples=False)
        ids = {s["id"] for s in data["structures"]} | {
            e["id"] for e in data["externals"]
        }
        for edge in data["edges"]:
            assert edge["f"] in ids, edge
            assert edge["t"] in ids, edge

    def test_packets_are_serializable_json(self):
        data = generate_atlas(include_real_samples=False)
        for packet in data["packets"]:
            assert packet["id"]
            assert packet["label"]
            json.dumps(packet["payload"])  # must serialize without error

    def test_layout_produces_painter_order(self):
        data = generate_atlas(include_real_samples=False)
        nodes = data["structures"] + data["externals"]
        for node in nodes:
            assert "gx" in node
            assert "gy" in node
            assert "px" in node
            assert "py" in node
            assert node["order"] == node["gx"] + node["gy"]

    def test_children_blocks_exist_for_apps_with_components(self):
        data = generate_atlas(include_real_samples=False)
        core = next(s for s in data["structures"] if s["id"] == "core")
        assert core["children"]
        for child in core["children"]:
            assert "what" in child
            assert "h" in child


class TestAtlasAdminViews:
    """Integration tests for the staff-only atlas pages."""

    def test_requires_staff_redirect(self, api_client):
        response = api_client.get("/admin/atlas/")
        assert response.status_code in (301, 302)

    def test_data_endpoint_requires_staff(self, api_client):
        response = api_client.get("/admin/atlas/data.json")
        assert response.status_code in (301, 302)

    def test_staff_can_view_page(self, api_client, staff_user):
        api_client.force_login(staff_user)
        response = api_client.get("/admin/atlas/")
        assert response.status_code == 200
        assert b"atlas-app" in response.content

    def test_staff_data_endpoint_returns_json(self, api_client, staff_user):
        api_client.force_login(staff_user)
        response = api_client.get("/admin/atlas/data.json")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("application/json")
        body = response.json()
        assert "structures" in body
        assert "edges" in body
        assert "packets" in body

    def test_regenerate_endpoint_redirects(self, api_client, staff_user):
        api_client.force_login(staff_user)
        response = api_client.post("/admin/atlas/regenerate/")
        assert response.status_code in (301, 302)
