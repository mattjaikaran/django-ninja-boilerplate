# Codebase Atlas

The Codebase Atlas renders your running Django project as an interactive
isometric city map inside the admin panel. Blocks are sized by real line
counts, edges carry animated data-flow dots, and every dot is a clickable
data packet — a snippet of real data transfer.

Open it at **Admin → Monitoring → Codebase Atlas** (`/admin/atlas/`).

## What you get

- **Blocks per app** — height scales with lines of code; hover for
  what/how, click for a detail panel with stats and endpoints.
- **Zoom into components** — drill into an app's controllers, services,
  models, schemas, admin, and tasks.
- **Data packets** — click a moving dot to inspect the JSON payload that
  crosses that edge. Packets come from the live OpenAPI schema (request and
  response shapes) and, when `ATLAS_REAL_SAMPLES` is on, from the most
  recent masked request bodies in the audit log.
- **Request trace** — play the canonical end-to-end flow (client → API →
  controller → service → model → database) with highlighted blocks.
- **Stats bar** — total LOC, apps, endpoints, models, test files, Django
  and Python versions. Every number is scanned from the real project.

## Usage

```bash
make atlas            # regenerate the data file (Docker)
make local-atlas      # regenerate locally (no Docker)
python manage.py atlas --output /tmp/atlas.json   # custom path
python manage.py atlas --no-samples               # skip audit mining
```

The admin page generates the data lazily on first view and caches it in
`atlas-data.json` (gitignored) for `ATLAS_CACHE_TTL` seconds. Use the
**Regenerate** button on the page to force a fresh scan.

## Configuration

All settings live in `api/settings/common.py`:

| Setting | Default | Purpose |
| ------- | ------- | ------- |
| `ATLAS_ENABLED` | `True` | Set `False` to remove the page and its URLs. |
| `ATLAS_DATA_PATH` | `BASE_DIR/atlas-data.json` | Where the generated JSON is cached. |
| `ATLAS_CACHE_TTL` | `3600` | Seconds before the admin page re-scans. |
| `ATLAS_REAL_SAMPLES` | `True` | Mine masked audit-log request bodies as data packets. |
| `ATLAS_METADATA` | `{}` | Optional dict of per-app prose (`{"core": {"what": ...}}`). |

## Adding prose to your apps

The generator counts lines and endpoints, but it cannot guess what an app
does. Add a small `atlas.py` to any app to fill the map's prose:

```python
# myapp/atlas.py
ATLAS = {
    "code": "MA",                      # short badge on the block
    "name": "My App",
    "what": "One sentence: what the app does.",
    "how": "One sentence: how it is built.",
    "children": {
        "controllers": {"name": "API", "what": "Endpoint layer"},
    },
}
```

See `core/atlas.py` and `todos/atlas.py` for complete examples. The
metadata keys `children`, `talks`, `w`, and `d` are optional.

## How it works

- `atlas/services/atlas_service.py` — orchestrator: discovers local apps,
  counts LOC, builds structures and externals.
- `atlas/services/introspect.py` — reads the live Ninja OpenAPI schema,
  maps endpoints to apps, builds edges, packets, and the trace.
- `atlas/services/samples.py` — deterministic sample payloads from the
  OpenAPI schemas plus masked audit-log samples.
- `atlas/services/layout.py` — zones, grid placement, iso projection.
- `atlas/management/commands/atlas.py` — the management command.
- `atlas/static/atlas/` — the renderer: `atlas-scene.js` (SVG city),
  `atlas.js` (interactions), `atlas-ui.js` (panels and overlays).
- `atlas/views.py` — three staff-only endpoints under `/admin/atlas/`.

The page is CSP-safe: the engine and stylesheet are static files, and the
data arrives over a same-origin JSON endpoint. No inline script or style.

To install this atlas in another Django backend, send
[docs/ATLAS_ADOPTION_PROMPT.md](../docs/ATLAS_ADOPTION_PROMPT.md) to your AI
coding assistant — it covers settings wiring, URL registration, the Unfold
dashboard, and the layout rules that keep the city readable.

## Security

All atlas endpoints require a staff account. Audit-log samples are masked
by the audit middleware before storage, and schema samples are generated
locally — the atlas never emits live secrets. The generator is a code
scanner: a down database or an import failure degrades gracefully instead
of breaking the admin page.
