"""Journey J-003: create, list, rotate and revoke an API key.

Calls the journey endpoints in order, the way the frontend will. Boundary
rules (auth, ownership, a foreign key returning 404) live in
``core/tests/test_route_auth.py``; do not copy them here.
"""

import json

import pytest


@pytest.mark.smoke
@pytest.mark.django_db
def test_j003_create_list_rotate_revoke(smoke_client, smoke_auth_headers):
    created = smoke_client.post(
        "/api/api-keys/",
        data=json.dumps({"name": "Journey key"}),
        content_type="application/json",
        **smoke_auth_headers,
    )
    assert created.status_code == 201
    body = created.json()
    key_id = body["id"]
    assert body["key"].startswith(f"{body['prefix']}.")
    assert body["name"] == "Journey key"

    listed = smoke_client.get("/api/api-keys/", **smoke_auth_headers)
    assert listed.status_code == 200
    assert [key["id"] for key in listed.json()] == [key_id]

    rotated = smoke_client.post(f"/api/api-keys/{key_id}/rotate", **smoke_auth_headers)
    assert rotated.status_code == 201
    rotated_body = rotated.json()
    new_id = rotated_body["id"]
    assert rotated_body["revokedKeyId"] == key_id
    assert rotated_body["newKey"] != body["key"]
    assert rotated_body["name"] == "Journey key"

    revoked = smoke_client.delete(f"/api/api-keys/{new_id}", **smoke_auth_headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True

    remaining = smoke_client.get("/api/api-keys/", **smoke_auth_headers)
    assert remaining.json() == []
