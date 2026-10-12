"""Data model for the product spec sync: paths, features, journeys, steps.

Pure Python on purpose: ``scripts/check_journeys.py`` imports it without
Django. The format is documented in ``docs/product/README.md``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

FEATURE_LINE = re.compile(r"^- \[( |x)\] (F-\d{3}) (.+)$")
CHECKBOX_LINE = re.compile(r"^\s*- \[.?\]")
AREA_HEADING = re.compile(r"^## (.+)$")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
JOURNEY_ID = re.compile(r"^J-\d{3}$")
STEP_ID = re.compile(r"^S\d+$")
FEATURE_ID = re.compile(r"^F-\d{3}$")
TICKET_ID = re.compile(r"^T-\d{3}$")
FILE_PREFIX = re.compile(r"^(J-\d{3})(?=-|\.md$)")
INLINE_TAG = re.compile(r"@(J-\d{3}(?:-S\d+)?)(?![\w-])")
BARE_TAG = re.compile(r"^@?(J-\d{3}(?:-S\d+)?)$")
TAG_PARTS = re.compile(r"^(J-\d{3})(?:-(S\d+))?$")
# `test.step('J-001-S2: Sign in', ...)` titles locate a step inside one test.
STEP_TITLE = re.compile(r"^\s*(J-\d{3}-S\d+)(?![\w-])")
STEP_SOURCE = re.compile(r"\.step\(\s*['\"`](J-\d{3}-S\d+)(?![\w-])")

STATUSES = ("draft", "building", "done")
E2E_GLOBS = ("**/*.spec.ts", "**/*.spec.js", "**/*.test.ts")

VERIFIED = "verified"
FAILING = "failing"
DOCUMENTED = "documented"
NO_RESULT = "no_result"
NO_SPEC = "no_spec"

PASSED = "passed"
FAILED = "failed"
SKIPPED = "skipped"


@dataclass(frozen=True)
class SpecPaths:
    """Resolved locations of the spec, the e2e suite, and the tickets."""

    spec_dir: Path
    e2e_dir: Path
    e2e_report: Path
    tickets_dir: Path

    @property
    def features_file(self) -> Path:
        return self.spec_dir / "FEATURES.md"

    @property
    def journeys_dir(self) -> Path:
        return self.spec_dir / "journeys"


def spec_paths(base_dir: Path, environ: Mapping[str, str] | None = None) -> SpecPaths:
    """Resolve the paths from env vars, with repo-relative defaults."""
    env = os.environ if environ is None else environ
    base = base_dir.resolve()

    def pick(name: str, default: Path) -> Path:
        value = env.get(name, "").strip()
        return Path(value).expanduser().resolve() if value else default.resolve()

    return SpecPaths(
        spec_dir=pick("JOURNEYS_SPEC_DIR", base / "docs" / "product"),
        e2e_dir=pick("JOURNEYS_E2E_DIR", base.parent / "frontend" / "e2e"),
        e2e_report=pick(
            "JOURNEYS_E2E_REPORT",
            base.parent / "frontend" / "test-results" / "journeys.json",
        ),
        tickets_dir=pick("TICKETS_DIR", base / "docs" / "tickets"),
    )


@dataclass(frozen=True)
class Issue:
    """One sync finding. ``ref`` is a feature, journey, step, or tag ID."""

    code: str
    message: str
    ref: str = ""
    path: str = ""


@dataclass(frozen=True)
class KnownIssue:
    step: str
    ticket: str
    note: str


@dataclass(frozen=True)
class E2eResult:
    """One Playwright spec from the JSON report.

    ``step_outcomes`` maps step tags found in ``test.step`` titles to their
    outcome. When it is set, it decides each step's state; a step tag absent
    from it did not run (the test stopped earlier).
    """

    title: str
    file: str
    tags: frozenset[str]
    outcome: str
    step_outcomes: Mapping[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.file} > {self.title}" if self.file else self.title

    def outcome_for(self, step_tag: str) -> str:
        """Return this test's outcome for one step."""
        if self.step_outcomes:
            return self.step_outcomes.get(step_tag, SKIPPED)
        return self.outcome


@dataclass
class Feature:
    id: str
    title: str
    area: str
    checked: bool
    line: int
    steps: list[str] = field(default_factory=list)
    verification: str = "unreferenced"


@dataclass
class Step:
    id: str
    title: str
    story: str
    features: list[str]
    acceptance: list[str]
    tag: str
    state: str = NO_SPEC
    spec_files: list[str] = field(default_factory=list)
    passing_tests: list[str] = field(default_factory=list)
    failing_tests: list[str] = field(default_factory=list)
    known_issue: KnownIssue | None = None
    missing: str = ""


@dataclass
class Journey:
    id: str
    title: str
    actor: str
    status: str
    path: str
    body: str
    steps: list[Step]
    known_issues: list[KnownIssue]
    failing_tests: list[str] = field(default_factory=list)

    @property
    def verified_steps(self) -> int:
        return sum(1 for step in self.steps if step.state == VERIFIED)

    @property
    def is_verified(self) -> bool:
        return self.verified_steps == len(self.steps) and not self.failing_tests


@dataclass
class SyncReport:
    paths: SpecPaths
    e2e_dir_exists: bool
    report_exists: bool
    features: list[Feature] = field(default_factory=list)
    journeys: list[Journey] = field(default_factory=list)
    tags_found: list[str] = field(default_factory=list)
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    gaps: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def verified_journeys(self) -> int:
        return sum(1 for journey in self.journeys if journey.is_verified)

    def journey(self, journey_id: str) -> Journey | None:
        return next((j for j in self.journeys if j.id == journey_id), None)

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "paths": {
                "spec_dir": str(self.paths.spec_dir),
                "e2e_dir": str(self.paths.e2e_dir),
                "e2e_report": str(self.paths.e2e_report),
                "tickets_dir": str(self.paths.tickets_dir),
            },
            "e2e_dir_exists": self.e2e_dir_exists,
            "report_exists": self.report_exists,
            "verified_journeys": self.verified_journeys,
            "features": [asdict(feature) for feature in self.features],
            "journeys": [
                {
                    **asdict(j),
                    "verified_steps": j.verified_steps,
                    "is_verified": j.is_verified,
                }
                for j in self.journeys
            ],
            "tags_found": self.tags_found,
            "errors": [asdict(issue) for issue in self.errors],
            "warnings": [asdict(issue) for issue in self.warnings],
            "gaps": [asdict(issue) for issue in self.gaps],
        }


class SpecFormatError(ValueError):
    """A journey file does not match the documented format."""
