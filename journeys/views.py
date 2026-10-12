"""Staff admin pages for user journeys.

- ``/admin/journeys/`` lists features and journeys with their verification.
- ``/admin/journeys/<id>/`` shows one journey step by step.

Both pages read ``docs/product/`` and the Playwright JSON report through
``journeys.services.spec_service``, the same code the JOURNEYS gate runs.
The pages are CSP-safe: no inline script or style.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from journeys.services import Issue, Journey, SyncReport, build_report, spec_paths

STEP_STATES = ("verified", "documented", "failing", "no_result", "no_spec")


def _report() -> SyncReport:
    return build_report(spec_paths(Path(settings.BASE_DIR)))


def _path_rows(report: SyncReport) -> list[dict[str, object]]:
    paths = report.paths
    rows = [
        ("Spec dir", "JOURNEYS_SPEC_DIR", paths.spec_dir, paths.spec_dir.is_dir()),
        ("E2E dir", "JOURNEYS_E2E_DIR", paths.e2e_dir, report.e2e_dir_exists),
        ("E2E report", "JOURNEYS_E2E_REPORT", paths.e2e_report, report.report_exists),
        ("Tickets dir", "TICKETS_DIR", paths.tickets_dir, paths.tickets_dir.is_dir()),
    ]
    return [
        {"label": label, "env": env, "path": str(path), "exists": exists}
        for label, env, path, exists in rows
    ]


def _journey_issues(report: SyncReport, journey: Journey) -> dict[str, list[Issue]]:
    def mine(issue: Issue) -> bool:
        return issue.path == journey.path or issue.ref.startswith(journey.id)

    return {
        "errors": [i for i in report.errors if mine(i)],
        "warnings": [i for i in report.warnings if mine(i)],
        "gaps": [i for i in report.gaps if mine(i)],
    }


def _body_blocks(body: str) -> list[dict[str, str]]:
    """Split the journey prose into headings and paragraphs (no markdown lib)."""
    blocks: list[dict[str, str]] = []
    for chunk in body.split("\n\n"):
        text = chunk.strip()
        if not text:
            continue
        if text.startswith("#") and "\n" not in text:
            blocks.append({"kind": "heading", "text": text.lstrip("#").strip()})
        else:
            blocks.append({"kind": "paragraph", "text": text})
    return blocks


@staff_member_required
@require_GET
def journeys_admin_view(request: HttpRequest) -> HttpResponse:
    """Render features, journeys, and sync findings inside the Unfold admin."""
    if not settings.JOURNEYS_ENABLED:
        return redirect("admin:index")
    report = _report()
    step_counts = Counter(step.state for j in report.journeys for step in j.steps)
    features = [
        {
            "feature": feature,
            "journeys": sorted({tag.split("-S")[0] for tag in feature.steps}),
        }
        for feature in report.features
    ]
    context = admin.site.each_context(request)
    context.update(
        {
            "title": "User journeys",
            "report": report,
            "features": features,
            "feature_count": len(report.features),
            "checked_count": sum(1 for f in report.features if f.checked),
            "step_counts": [
                (state, step_counts.get(state, 0)) for state in STEP_STATES
            ],
            "path_rows": _path_rows(report),
        }
    )
    return render(request, "journeys/journeys.html", context)


@staff_member_required
@require_GET
def journey_detail_view(request: HttpRequest, journey_id: str) -> HttpResponse:
    """Render one journey step by step, with what is missing at each step."""
    if not settings.JOURNEYS_ENABLED:
        return redirect("admin:index")
    report = _report()
    journey = report.journey(journey_id)
    if journey is None:
        raise Http404(f"No journey {journey_id}")
    titles = {feature.id: feature.title for feature in report.features}
    steps = [
        {
            "step": step,
            "features": [(fid, titles.get(fid, "unknown")) for fid in step.features],
        }
        for step in journey.steps
    ]
    context = admin.site.each_context(request)
    context.update(
        {
            "title": f"{journey.id} {journey.title}",
            "journey": journey,
            "steps": steps,
            "issues": _journey_issues(report, journey),
            "body_blocks": _body_blocks(journey.body),
            "spec_dir": report.paths.spec_dir,
        }
    )
    return render(request, "journeys/journey_detail.html", context)
