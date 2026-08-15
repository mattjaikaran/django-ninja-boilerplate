"""Admin views for the Codebase Atlas.

Three staff-only endpoints:

- ``/admin/atlas/`` — the interactive map page (Unfold admin chrome)
- ``/admin/atlas/data.json`` — the generated atlas data for the renderer
- ``/admin/atlas/regenerate/`` — POST to force a fresh scan

The data endpoint keeps the page CSP-safe: no inline script or style, the
engine and stylesheet load as static files, and the JSON arrives over a
same-origin fetch.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from atlas.services.atlas_service import load_or_generate

ADMIN_ATLAS_URL = "admin/atlas/"


def _static_version() -> str:
    """Latest mtime of the atlas assets, for cache-busting URLs.

    The static server sends no cache headers, so browsers apply heuristic
    caching and keep serving a stale renderer after edits. Tacking the
    newest asset mtime onto the URLs forces a refetch whenever a file
    changes.
    """
    newest: float = 0.0
    static_dir = Path(__file__).resolve().parent / "static" / "atlas"
    for path in static_dir.glob("*.{css,js}"):
        newest = max(newest, path.stat().st_mtime)
    return str(int(newest))


@staff_member_required
@require_GET
def atlas_admin_view(request):
    """Render the interactive atlas page inside the Unfold admin."""
    if not getattr(settings, "ATLAS_ENABLED", True):
        return redirect("admin:index")
    data = load_or_generate()
    context = admin.site.each_context(request)
    context.update(
        {
            "title": "Codebase Atlas",
            "subtitle": (
                f"{data['meta']['project']} — {data['meta']['app_count']} apps, "
                f"{data['meta']['endpoint_count']} endpoints, "
                f"{data['meta']['total_loc']} LOC"
            ),
            "atlas_data_url": "/admin/atlas/data.json",
            "atlas_regenerate_url": reverse("atlas_regenerate"),
            "atlas_generated_at": data["meta"].get("generated_at", ""),
            "atlas_static_version": _static_version(),
        }
    )
    return render(request, "atlas/atlas.html", context)


@staff_member_required
@require_GET
def atlas_data_view(request):
    """Return the atlas data as JSON for the renderer."""
    return JsonResponse(load_or_generate())


@staff_member_required
@require_POST
def atlas_regenerate_view(request):
    """Force a fresh scan and reload the page."""
    load_or_generate(force=True)
    return redirect("atlas_admin")
