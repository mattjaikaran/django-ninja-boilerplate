"""Boundaries of the journeys app: staff-only pages and the sync contract.

The contract tests build a real spec dir, e2e dir, tickets dir, and
Playwright JSON report under ``tmp_path``. Nothing is mocked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from journeys.services import SyncReport, build_report, spec_paths

FEATURES = "# Features\n\n## Accounts\n\n- [{mark}] F-001 Sign in\n"

JOURNEY = """---
id: J-001
title: Sign in
actor: Visitor
status: {status}
steps:
  - id: S1
    title: Open the sign-in page
    features: [F-001]
  - id: S2
    title: Submit credentials
    features: [F-001]
{known_issues}---

## Goal

Sign in.
"""

KNOWN_ISSUE = (
    "known_issues:\n  - step: S2\n    ticket: T-004\n    note: Spinner never stops.\n"
)


def _spec(title: str, tags: list[str], passed: bool) -> dict[str, object]:
    result = "passed" if passed else "failed"
    status = "expected" if passed else "unexpected"
    return {
        "title": title,
        "tags": tags,
        "tests": [{"status": status, "results": [{"status": result}]}],
    }


def _report(
    tmp_path: Path,
    *,
    status: str = "building",
    mark: str = " ",
    known_issues: str = "",
    source: str = "",
    specs: list[dict[str, object]] | None = None,
) -> SyncReport:
    spec_dir = tmp_path / "product"
    (spec_dir / "journeys").mkdir(parents=True)
    (spec_dir / "FEATURES.md").write_text(FEATURES.format(mark=mark))
    (spec_dir / "journeys" / "J-001-sign-in.md").write_text(
        JOURNEY.format(status=status, known_issues=known_issues)
    )
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    (tickets / "T-004-fix-login-spinner.md").write_text("---\nid: T-004\n---\n")
    e2e = tmp_path / "e2e"
    e2e.mkdir()
    (e2e / "sign-in.spec.ts").write_text(source)
    report_file = tmp_path / "journeys.json"
    suite = {
        "title": "sign-in.spec.ts",
        "file": "sign-in.spec.ts",
        "specs": specs or [],
    }
    report_file.write_text(json.dumps({"suites": [suite]}))
    paths = spec_paths(
        tmp_path,
        environ={
            "JOURNEYS_SPEC_DIR": str(spec_dir),
            "JOURNEYS_E2E_DIR": str(e2e),
            "JOURNEYS_E2E_REPORT": str(report_file),
            "TICKETS_DIR": str(tickets),
        },
    )
    return build_report(paths)


SOURCE = "test('sign in', { tag: ['@J-001-S1', '@J-001-S2'] }, async () => {});\n"
S1_PASSES = _spec("opens the page", ["J-001-S1"], passed=True)
S2_FAILS = _spec("submits credentials", ["@J-001-S2"], passed=False)


ORPHAN_SOURCE = SOURCE + "test('old', { tag: ['@J-001-S9'] }, async () => {});\n"
# One full-journey test that stops at S1: S2 never ran, so only S1 fails.
STOPS_AT_S1 = {
    "title": "signs in",
    "tags": ["J-001"],
    "tests": [
        {
            "status": "unexpected",
            "results": [
                {
                    "status": "failed",
                    "steps": [{"title": "J-001-S1: open", "error": {"message": "x"}}],
                }
            ],
        }
    ],
}


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        pytest.param(
            {"status": "done", "source": SOURCE, "specs": [S1_PASSES, S2_FAILS]},
            [
                ("undocumented_failure", "J-001-S2"),
                ("done_not_verified", "J-001-S2"),
            ],
            id="done-journey-with-failing-test",
        ),
        pytest.param(
            {
                "known_issues": KNOWN_ISSUE,
                "source": SOURCE,
                "specs": [S1_PASSES, S2_FAILS],
            },
            [],
            id="documented-failure-on-building-journey",
        ),
        pytest.param(
            {"mark": "x", "source": SOURCE, "specs": [S1_PASSES]},
            [("feature_checked_unverified", "F-001")],
            id="checked-feature-with-unverified-step",
        ),
        pytest.param(
            {"source": ORPHAN_SOURCE, "specs": [S1_PASSES]},
            [("orphan_tag", "J-001-S9")],
            id="orphan-test-tag",
        ),
        pytest.param(
            {"source": "test('signs in', { tag: '@J-001' })", "specs": [STOPS_AT_S1]},
            [("undocumented_failure", "J-001-S1")],
            id="failure-located-by-step-title",
        ),
    ],
)
def test_sync_rules(tmp_path, case, expected):
    report = _report(tmp_path, **case)

    assert [(issue.code, issue.ref) for issue in report.errors] == expected


@pytest.mark.django_db
class TestAdminPages:
    def test_anonymous_is_redirected(self, client):
        response = client.get("/admin/journeys/")

        assert response.status_code == 302

    def test_staff_sees_overview_and_detail(self, client, staff_user):
        client.force_login(staff_user)

        assert client.get("/admin/journeys/").status_code == 200
        assert client.get("/admin/journeys/J-001/").status_code == 200
        assert client.get("/admin/journeys/J-999/").status_code == 404
