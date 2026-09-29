# Atlas architecture

## Modules

| Path | Role |
|---|---|
| `atlas/apps.py` | `AtlasConfig` |
| `atlas/views.py` | Admin views: page, `data.json`, regenerate |
| `atlas/services/` | Graph builder and cache writer |
| `atlas/templates/` | Unfold-styled admin templates |
| `atlas/static/atlas/` | Scene and layout JavaScript |
| `atlas/management/commands/` | The `atlas` command |
| `core/atlas.py` | Metadata contract and defaults |
| `atlas-data.json` | Generated cache at the repo root |
| `<app>/atlas.py` | Per-app prose metadata |

## Metadata contract

```python
ATLAS = {
    "code": "XX",
    "name": "Example",
    "what": "One sentence on what the app does.",
    "how": "One sentence on how it is built.",
    "children": {
        "controllers": {"name": "Controllers", "what": "..."},
        "services": {"name": "Services", "what": "..."},
    },
}
```

`what` answers "what does it do", `how` answers "how is it built", and `children`
describes the inside view. Keep each value to one sentence.

## Routes

Mounted in `api/urls.py` before the admin catch-all:

| Path | View |
|---|---|
| `/admin/atlas/` | `atlas_admin_view` |
| `/admin/atlas/data.json` | `atlas_data_view` |
| `/admin/atlas/regenerate/` | `atlas_regenerate_view` |

## Regeneration flow

1. The generator scans `*/models.py`, `*/services/`, and `*/controllers/` for
   import relationships and reads each app's `atlas.py`.
2. It writes `atlas-data.json`.
3. The admin page reads the cache and renders the scene.
4. `just update-architecture` reruns the generator.

The refresh must not require manual diagram editing. If the map is stale, rerun
the command; do not hand-edit `atlas-data.json`.
