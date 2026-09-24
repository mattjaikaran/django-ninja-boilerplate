---
name: system-design-atlas
description: >
  Use when working with the codebase atlas: the interactive architecture map in
  the Django admin, its cached data file, or regenerating it. Use when the user
  mentions "atlas", "architecture map", "dependency graph", "deployment graph",
  "system design", or "update-architecture".
---

# System design atlas

The `atlas/` app renders an interactive map of the codebase in the Unfold admin
at `/admin/atlas/`. It is generated, cached, and staff-only.

## When to use this skill

- Adding an app or module and wanting it on the map
- Regenerating the map after structural changes
- Debugging an empty or stale map

## How it works

- `core/atlas.py` documents the metadata shape.
- Each app may ship an `atlas.py` module with an `ATLAS` dict: `code`, `name`,
  `what`, `how`, and `children`. See `todos/atlas.py`, `decisions/atlas.py`.
- The generator writes `atlas-data.json` at the repo root.
- The map is gated by `ATLAS_ENABLED` and served by `atlas/views.py` behind the
  staff permission.

New app? Add an `atlas.py` beside its `apps.py` so the map describes it.

## Regenerate

```bash
just update-architecture              # docker compose exec django python manage.py atlas
uv run python manage.py atlas         # direct, if settings are importable
```

The refreshed data is cached; the admin page reads the cache.

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `ATLAS_ENABLED` | `True` | Master switch |
| `ATLAS_DATA_PATH` | `<repo>/atlas-data.json` | Cache location |
| `ATLAS_CACHE_TTL` | `3600` | Cache lifetime, seconds |
| `ATLAS_REAL_SAMPLES` | `True` | Mine masked audit-log bodies for data packets |

## Verify

```bash
uv run pytest atlas/
```

Then open `/admin/atlas/` as a staff user and confirm the new block appears.

See `references/atlas-architecture.md` for the module map.
