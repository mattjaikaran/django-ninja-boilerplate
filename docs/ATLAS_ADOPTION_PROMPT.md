# Atlas Adoption Prompt

Copy this entire message and send it to your AI coding assistant (Claude Code,
Cursor, Copilot, etc.) in any Django backend to install the Codebase Atlas admin
page and the matching admin dashboard. The prompt assumes the target project
already uses django-unfold. If it does not, install django-unfold first.

---

## Instructions for the AI

Install the interactive Codebase Atlas into this Django admin. The atlas is an
isometric map of the codebase rendered at `/admin/atlas/` inside the Unfold
admin chrome. A working reference implementation lives in the
`django-ninja-boilerplate` project — copy the `atlas/` app from there and adapt
the settings and URL wiring to this project. Do not rewrite the renderer.

### Step 1: Copy the atlas app

Copy the `atlas/` package from the reference project (or apply this file
structure) into the project root:

```
atlas/
  apps.py                # AppConfig, label "atlas", add to INSTALLED_APPS
  views.py               # 3 staff-only views: page, data.json, regenerate
  services/
    introspect.py        # scans Django apps/models/endpoints/tasks
    atlas_service.py     # orchestrates scan, caches atlas-data.json
    layout.py            # iso grid placement, zones, heights
    samples.py           # synthetic data when the scan finds nothing
  static/atlas/          # atlas.css, atlas.js, atlas-scene.js, atlas-ui.js
  templates/atlas/       # atlas.html (extends unfold/layouts/base.html)
  management/commands/atlas.py   # CLI: python manage.py atlas
  tests/test_atlas.py
```

### Step 2: Wire the settings

In `settings/common.py` (or the settings module your project loads):

1. Add `"atlas"` to `INSTALLED_APPS`.
2. Add the atlas config block:

```python
# Codebase Atlas Configuration
ATLAS_ENABLED = env("ATLAS_ENABLED", default=True)
ATLAS_DATA_PATH = BASE_DIR / "atlas-data.json"
```

3. **Critical:** if the project keeps Unfold settings in a separate module
   (e.g. `api/settings/unfold.py`), that module MUST be imported. A common bug
   is leaving it orphaned — then `DASHBOARD_CALLBACK` never runs and the admin
   dashboard renders without stats or recent activity. Add at the end of the
   settings module:

```python
from .unfold import UNFOLD  # noqa: E402
```

4. In the Unfold settings, add the sidebar item and dashboard callback:

```python
UNFOLD = {
    "DASHBOARD_CALLBACK": "core.admin.dashboard.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,  # lists every app + model automatically
        "navigation": [
            {"title": "Monitoring", "items": [
                {"title": "Codebase Atlas", "icon": "map",
                 "link": "/admin/atlas/"},
            ]},
        ],
    },
}
```

Do NOT hardcode per-model links such as `/admin/auth/user/` in the sidebar
unless the model actually lives there — use `/admin/<app_label>/<model>/` and
check the app label (custom user models usually live in `core`, not `auth`).

### Step 3: Wire the URLs

Add the atlas URLs BEFORE the admin catch-all in the root urlconf:

```python
from atlas.views import atlas_admin_view, atlas_data_view, atlas_regenerate_view

urlpatterns = [
    path("admin/atlas/data.json", atlas_data_view, name="atlas_data"),
    path("admin/atlas/regenerate/", atlas_regenerate_view, name="atlas_regenerate"),
    path("admin/atlas/", atlas_admin_view, name="atlas_admin"),
    path("admin/", admin.site.urls),
]
```

### Step 4: Add the dashboard

Create `core/admin/dashboard.py` with a `dashboard_callback(request, context)`
that returns the context plus:

- `context["stats_cards"]` — list of dicts `{title, value, description, icon,
  color}` where `color` is one of the Tailwind color scales Unfold compiles:
  `primary`, `blue`, `green`, `orange` (NOT `success`/`info`/`warning`).
- `context["quick_links"]` — include `{"title": "Codebase Atlas",
  "url": "/admin/atlas/", "icon": "map"}`.
- `context["recent_activity"]` — list of `{user, action, target, time}` dicts.

If the project has a custom admin index template, see Step 5. Otherwise the
dashboard callback alone is enough.

### Step 5: Admin index template (only if the project overrides it)

If `templates/admin/index.html` exists and renders custom dashboard markup,
rewrite it with these hard rules:

1. Only use Tailwind utility classes that exist in the compiled Unfold
   stylesheet. Unfold ships a precompiled `styles.css` containing ONLY the
   classes its own templates use. `dark:bg-gray-800`, `text-gray-900`,
   `divide-y`, `lg:grid-cols-3` and similar vanilla-Tailwind classes are
   usually MISSING and silently do nothing — the card stays white in dark mode.
   Verified-available alternatives: `bg-white dark:bg-base-900`,
   `border border-base-200 dark:border-base-800`, `rounded-default`,
   `shadow-xs`, `text-important`, `text-base-500 dark:text-base-400`,
   `bg-base-50 dark:bg-base-800`, `grid grid-cols-1 md:grid-cols-2
   lg:grid-cols-4`, `flex flex-col lg:flex-row`.
2. Render the app list explicitly:
   `{% include "unfold/helpers/app_list_default.html" with show_changelinks=True %}`
   — do NOT use `{{ block.super }}` inside `{% block content %}`; it renders the
   empty `{{ content }}` variable and the app list silently disappears.
3. Verify dark mode after editing: toggle the theme in the admin and confirm
   cards, borders, and text all use the `dark:` variants.

### Step 6: Verify

1. `python manage.py atlas` — writes `atlas-data.json`.
2. `python manage.py collectstatic --noinput` — the atlas static files must be
   served. In development with `DEBUG=True` runserver serves them from the app
   static dir automatically.
3. Open `/admin/atlas/` as a staff user. Expect:
   - An isometric city: tall towers at the back, short slabs in front.
   - No overlapping blocks and no overlapping labels.
   - A control bar below the canvas with legend, zoom, trace, and stats.
4. Open `/admin/`. Expect stats cards, quick links (including Codebase Atlas),
   the full app list, and a readable Recent Activity panel in both light and
   dark mode.
5. Run the atlas tests: `python manage.py test atlas`.

### Critical rules for the renderer and layout

These are the fixes that make the atlas look right. Do not regress them:

1. **Cube faces use full dimensions.** In `atlas-scene.js` `cubeFaces()`, the
   offsets must be `node.w * TILE_W` / `node.d * TILE_W`, NOT `(node.w - 1)` /
   `(node.d - 1)`. The off-by-one makes every cube degenerate (zero-area faces)
   and the city renders as overlapping text.
2. **Labels sit on the left face, title-cased.** Long names fall back to the
   id. Never force `textLength`/`lengthAdjust` squishing — it looks broken.
3. **Layout order: tallest zone first, smallest gy first.** Short blocks must
   sit in front of tall towers; otherwise the tower hides everything behind it.
4. **Rows never overlap.** Keep a full tile gap between columns and 3 rows
   between zones. A wrapped row shifts two tiles right so it never collides
   with the row above.
5. **Controls live outside the canvas.** Legend, zoom, trace, and stats belong
   in a `.atlas-controls` bar below the canvas — absolutely-positioned overlays
   inside the canvas collide with blocks and labels.
6. **Static files are CSP-safe.** No inline `<script>` or `<style>` in the
   template; load CSS via `{% block extrastyle %}` and JS via
   `{% block extrahead %}` with `defer`.
