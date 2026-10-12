---
id: J-003
title: Manage API keys
actor: Developer
status: building
steps:
  - id: S1
    title: Create an API key
    story: As a developer, I want to create an API key, so that my scripts can call the API.
    features: [F-009]
    acceptance:
      - The page shows the full key once, with a copy button.
      - After I leave the page, only the key prefix is visible.
  - id: S2
    title: List my API keys
    story: As a developer, I want to see my API keys, so that I know which ones are active.
    features: [F-009]
    acceptance:
      - The list shows the name, prefix, and creation date of each key.
  - id: S3
    title: Rotate an API key
    story: As a developer, I want to rotate a key, so that I can replace a leaked secret.
    features: [F-009]
    acceptance:
      - Rotation shows the new key once.
      - The old key stops working.
  - id: S4
    title: Revoke an API key
    story: As a developer, I want to revoke a key, so that it can no longer call the API.
    features: [F-009]
    acceptance:
      - The revoked key leaves the active list.
      - A request with the revoked key is rejected.
---

## Goal

A developer creates, lists, rotates, and revokes API keys.

## Context

- Create calls `POST /api/api-keys/`. The raw key (`{prefix}.{secret}`) is
  in the response only once.
- The list calls `GET /api/api-keys/`. Revoked keys appear only with
  `include_revoked=true`.
- Rotate calls `POST /api/api-keys/{key_id}/rotate`. Revoke calls
  `DELETE /api/api-keys/{key_id}`.
- Scripts send the key in the `X-API-Key` header. See `docs/API_KEYS.md`.

## Notes

Start from J-001 S2 (signed in).
