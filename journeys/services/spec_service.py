"""Product spec sync: features, user journeys, and Playwright evidence.

Pure Python on purpose. The admin views and the standalone gate
(``scripts/check_journeys.py``) both import this module, so it must not
import Django. The format and the sync rules are documented in
``docs/product/README.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from .e2e_evidence import load_results, scan_sources
from .spec_models import (
    AREA_HEADING,
    CHECKBOX_LINE,
    DOCUMENTED,
    FAILED,
    FAILING,
    FEATURE_ID,
    FEATURE_LINE,
    FILE_PREFIX,
    FRONTMATTER,
    JOURNEY_ID,
    NO_RESULT,
    NO_SPEC,
    PASSED,
    STATUSES,
    STEP_ID,
    TAG_PARTS,
    TICKET_ID,
    VERIFIED,
    E2eResult,
    Feature,
    Issue,
    Journey,
    KnownIssue,
    SpecFormatError,
    SpecPaths,
    Step,
    SyncReport,
    spec_paths,
)

__all__ = [
    "Feature",
    "Issue",
    "Journey",
    "KnownIssue",
    "SpecFormatError",
    "SpecPaths",
    "Step",
    "SyncReport",
    "build_report",
    "parse_journey",
    "spec_paths",
]

# ── Parsing ──────────────────────────────────────────────────────────


def _req_str(data: Mapping[str, object], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SpecFormatError(f"{where}: '{key}' must be a non-empty string")
    return value.strip()


def _opt_str(data: Mapping[str, object], key: str, where: str) -> str:
    value = data.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SpecFormatError(f"{where}: '{key}' must be a string")
    return value.strip()


def _str_list(data: Mapping[str, object], key: str, where: str) -> list[str]:
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SpecFormatError(f"{where}: '{key}' must be a list of strings")
    return [item.strip() for item in value]


def _mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise SpecFormatError(f"{where}: must be a mapping")
    return value


def _parse_step(journey_id: str, index: int, raw: object) -> Step:
    data = _mapping(raw, f"steps[{index}]")
    step_id = _req_str(data, "id", f"steps[{index}]")
    if not STEP_ID.match(step_id):
        raise SpecFormatError(f"steps[{index}]: id {step_id!r} must look like S1")
    where = f"step {step_id}"
    features = _str_list(data, "features", where)
    for feature_id in features:
        if not FEATURE_ID.match(feature_id):
            raise SpecFormatError(
                f"{where}: feature {feature_id!r} must look like F-001"
            )
    return Step(
        id=step_id,
        title=_req_str(data, "title", where),
        story=_opt_str(data, "story", where),
        features=features,
        acceptance=_str_list(data, "acceptance", where),
        tag=f"{journey_id}-{step_id}",
    )


def _parse_known_issue(index: int, raw: object) -> KnownIssue:
    where = f"known_issues[{index}]"
    data = _mapping(raw, where)
    ticket = _req_str(data, "ticket", where)
    if not TICKET_ID.match(ticket):
        raise SpecFormatError(f"{where}: ticket {ticket!r} must look like T-001")
    return KnownIssue(
        step=_req_str(data, "step", where),
        ticket=ticket,
        note=_opt_str(data, "note", where),
    )


def parse_journey(text: str, rel_path: str) -> Journey:
    """Parse one journey file. Raises ``SpecFormatError`` on bad frontmatter."""
    text = text.replace("\r\n", "\n")
    match = FRONTMATTER.match(text)
    if not match:
        raise SpecFormatError("missing YAML frontmatter between '---' lines")
    try:
        raw: object = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise SpecFormatError(f"invalid YAML: {str(exc).splitlines()[0]}") from exc
    data = _mapping(raw, "frontmatter")
    journey_id = _req_str(data, "id", "frontmatter")
    if not JOURNEY_ID.match(journey_id):
        raise SpecFormatError(f"id {journey_id!r} must look like J-001")
    status = _req_str(data, "status", "frontmatter")
    if status not in STATUSES:
        raise SpecFormatError(f"status {status!r} must be one of {', '.join(STATUSES)}")
    steps_raw = data.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise SpecFormatError("'steps' must be a non-empty list")
    issues_raw = data.get("known_issues")
    if issues_raw is not None and not isinstance(issues_raw, list):
        raise SpecFormatError("'known_issues' must be a list")
    return Journey(
        id=journey_id,
        title=_req_str(data, "title", "frontmatter"),
        actor=_req_str(data, "actor", "frontmatter"),
        status=status,
        path=rel_path,
        body=text[match.end() :].strip(),
        steps=[_parse_step(journey_id, i, item) for i, item in enumerate(steps_raw, 1)],
        known_issues=[
            _parse_known_issue(i, item) for i, item in enumerate(issues_raw or [], 1)
        ],
    )


def _load_features(paths: SpecPaths, report: SyncReport) -> None:
    rel = paths.features_file.name
    try:
        text = paths.features_file.read_text(encoding="utf-8")
    except OSError as exc:
        report.errors.append(
            Issue(
                "missing_features_file",
                f"cannot read {paths.features_file}: {exc}",
                path=rel,
            )
        )
        return
    seen: set[str] = set()
    area = ""
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.rstrip()
        if stripped.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = AREA_HEADING.match(stripped)
        if heading:
            area = heading.group(1).strip()
            continue
        match = FEATURE_LINE.match(stripped)
        if match is None:
            if CHECKBOX_LINE.match(stripped):
                report.errors.append(
                    Issue(
                        "bad_feature_line",
                        f"line {lineno} must match '- [ ] F-001 Title': {stripped!r}",
                        path=f"{rel}:{lineno}",
                    )
                )
            continue
        feature_id = match.group(2)
        if feature_id in seen:
            report.errors.append(
                Issue(
                    "duplicate_id",
                    f"feature {feature_id} is defined twice",
                    feature_id,
                    rel,
                )
            )
            continue
        seen.add(feature_id)
        report.features.append(
            Feature(
                feature_id, match.group(3).strip(), area, match.group(1) == "x", lineno
            )
        )


def _load_journeys(paths: SpecPaths, report: SyncReport) -> set[str]:
    """Parse every journey file. Returns IDs of journeys that failed to parse."""
    broken: set[str] = set()
    if not paths.journeys_dir.is_dir():
        return broken
    for path in sorted(paths.journeys_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        rel = f"journeys/{path.name}"
        prefix = FILE_PREFIX.match(path.name)
        try:
            journey = parse_journey(path.read_text(encoding="utf-8"), rel)
        except (OSError, SpecFormatError) as exc:
            report.errors.append(Issue("bad_frontmatter", str(exc), path=rel))
            if prefix:
                broken.add(prefix.group(1))
            continue
        if prefix is None or prefix.group(1) != journey.id:
            report.errors.append(
                Issue(
                    "id_filename_mismatch",
                    f"file name must start with '{journey.id}-' to match its id",
                    journey.id,
                    rel,
                )
            )
        if report.journey(journey.id) is not None:
            report.errors.append(
                Issue(
                    "duplicate_id",
                    f"journey {journey.id} is defined twice",
                    journey.id,
                    rel,
                )
            )
            continue
        report.journeys.append(journey)
    report.journeys.sort(key=lambda journey: journey.id)
    return broken


# ── Sync rules ───────────────────────────────────────────────────────


def _ticket_exists(tickets_dir: Path, ticket: str) -> bool:
    if (tickets_dir / f"{ticket}.md").is_file():
        return True
    return tickets_dir.is_dir() and any(tickets_dir.glob(f"{ticket}-*.md"))


def _missing_text(step: Step) -> str:
    journey_tag = step.tag.rsplit("-", 1)[0]
    if step.state == VERIFIED:
        return "Nothing. The step passed in the last report."
    if step.state == DOCUMENTED and step.known_issue is not None:
        issue = step.known_issue
        return (
            f"Known issue {issue.ticket}: {issue.note or 'no note'}. Fix it, make "
            f"step {step.tag} pass, then remove the known_issues entry."
        )
    if step.state == FAILING:
        return (
            f"Step {step.tag} fails. Fix the product or the test, or record a "
            "known_issues entry with a ticket."
        )
    if step.state == NO_RESULT:
        return (
            f"The report has no result for {step.tag}: the suite did not run, or "
            "an earlier step failed. Run Playwright with the JSON reporter."
        )
    return (
        f"No test covers it. Add test.step('{step.tag}: ...') to the "
        f"@{journey_tag} journey test in the frontend."
    )


def _evaluate_step(
    step: Step,
    source_tags: Mapping[str, set[str]],
    results: list[E2eResult],
    known: KnownIssue | None,
) -> None:
    tagged = [r for r in results if step.tag in r.tags]
    files = set(source_tags.get(step.tag, set()))
    files.update(r.file for r in tagged if r.file)
    step.spec_files = sorted(files)
    step.failing_tests = [r.label for r in tagged if r.outcome_for(step.tag) == FAILED]
    step.passing_tests = [r.label for r in tagged if r.outcome_for(step.tag) == PASSED]
    if step.failing_tests:
        step.state = FAILING
    elif step.passing_tests:
        step.state = VERIFIED
    elif step.tag in source_tags or tagged:
        step.state = NO_RESULT
    else:
        step.state = NO_SPEC
    if step.state != VERIFIED and known is not None:
        step.state = DOCUMENTED
        step.known_issue = known
    step.missing = _missing_text(step)


def _resolve_journey(
    journey: Journey,
    feature_ids: set[str],
    source_tags: Mapping[str, set[str]],
    results: list[E2eResult],
    paths: SpecPaths,
    report: SyncReport,
) -> None:
    rel = journey.path
    step_ids: set[str] = set()
    for step in journey.steps:
        if step.id in step_ids:
            report.errors.append(
                Issue("duplicate_id", f"step {step.id} is defined twice", step.tag, rel)
            )
        step_ids.add(step.id)
        for feature_id in step.features:
            if feature_id not in feature_ids:
                report.errors.append(
                    Issue(
                        "unknown_feature",
                        f"{step.tag} references {feature_id}, which is not in FEATURES.md",
                        step.tag,
                        rel,
                    )
                )
    known: dict[str, KnownIssue] = {}
    for issue in journey.known_issues:
        if issue.step not in step_ids:
            report.errors.append(
                Issue(
                    "unknown_step",
                    f"known issue {issue.ticket} references unknown step {issue.step}",
                    journey.id,
                    rel,
                )
            )
        if not _ticket_exists(paths.tickets_dir, issue.ticket):
            report.errors.append(
                Issue(
                    "missing_ticket",
                    f"known issue on {issue.step} references {issue.ticket}, "
                    f"but no {issue.ticket}-*.md exists in {paths.tickets_dir}",
                    journey.id,
                    rel,
                )
            )
        known.setdefault(issue.step, issue)
    done = journey.status == "done"
    if done and journey.known_issues:
        report.errors.append(
            Issue(
                "done_with_known_issues",
                f"{journey.id} is done but lists {len(journey.known_issues)} known issue(s)",
                journey.id,
                rel,
            )
        )
    journey.failing_tests = [
        r.label for r in results if journey.id in r.tags and r.outcome == FAILED
    ]
    if done and journey.failing_tests:
        report.errors.append(
            Issue(
                "done_not_verified",
                f"{journey.id} is done but a @{journey.id} test failed: "
                f"{journey.failing_tests[0]}",
                journey.id,
                rel,
            )
        )
    for step in journey.steps:
        _evaluate_step(step, source_tags, results, known.get(step.id))
        label = f"{step.tag} {step.title}"
        if step.state == FAILING:
            report.errors.append(
                Issue(
                    "undocumented_failure",
                    f"{label}: a tagged test fails and no known_issues entry covers it",
                    step.tag,
                    rel,
                )
            )
        if done and step.state != VERIFIED:
            report.errors.append(
                Issue(
                    "done_not_verified",
                    f"{journey.id} is done but {step.tag} is {step.state}",
                    step.tag,
                    rel,
                )
            )
        elif not done and step.state in (NO_SPEC, NO_RESULT):
            what = "no tagged test" if step.state == NO_SPEC else "no test result"
            report.gaps.append(Issue(step.state, f"{label}: {what}", step.tag, rel))


def _check_orphans(tags: set[str], report: SyncReport, broken: set[str]) -> None:
    steps = {j.id: {s.id for s in j.steps} for j in report.journeys}
    for tag in sorted(tags):
        match = TAG_PARTS.match(tag)
        if match is None:
            continue
        journey_id, step_id = match.group(1), match.group(2)
        if journey_id in broken:
            continue
        if journey_id not in steps:
            reason = f"journey {journey_id} does not exist"
        elif step_id is not None and step_id not in steps[journey_id]:
            reason = f"{journey_id} has no step {step_id}"
        else:
            continue
        report.errors.append(Issue("orphan_tag", f"test tag @{tag}: {reason}", tag))


def _check_features(report: SyncReport) -> None:
    states: dict[str, str] = {}
    for journey in report.journeys:
        for step in journey.steps:
            states[step.tag] = step.state
            for feature in report.features:
                if feature.id in step.features and step.tag not in feature.steps:
                    feature.steps.append(step.tag)
    for feature in report.features:
        unverified = [tag for tag in feature.steps if states[tag] != VERIFIED]
        if not feature.steps:
            feature.verification = "unreferenced"
        elif not unverified:
            feature.verification = VERIFIED
        elif len(unverified) < len(feature.steps):
            feature.verification = "partial"
        else:
            feature.verification = "unverified"
        rel = f"FEATURES.md:{feature.line}"
        if feature.checked and not feature.steps:
            report.errors.append(
                Issue(
                    "feature_checked_unreferenced",
                    f"{feature.id} is checked but no journey step references it",
                    feature.id,
                    rel,
                )
            )
        elif feature.checked and unverified:
            report.errors.append(
                Issue(
                    "feature_checked_unverified",
                    f"{feature.id} is checked but these steps are not verified: "
                    f"{', '.join(unverified)}",
                    feature.id,
                    rel,
                )
            )
        elif not feature.checked and feature.verification == VERIFIED:
            report.warnings.append(
                Issue(
                    "feature_ready",
                    f"{feature.id} has every referencing step verified; check it off",
                    feature.id,
                    rel,
                )
            )


def build_report(paths: SpecPaths) -> SyncReport:
    """Read the spec and the e2e evidence, then apply every sync rule."""
    report = SyncReport(
        paths=paths,
        e2e_dir_exists=paths.e2e_dir.is_dir(),
        report_exists=paths.e2e_report.is_file(),
    )
    _load_features(paths, report)
    broken = _load_journeys(paths, report)
    source_tags = scan_sources(paths.e2e_dir)
    results = load_results(paths.e2e_report, report.warnings)
    feature_ids = {feature.id for feature in report.features}
    for journey in report.journeys:
        _resolve_journey(journey, feature_ids, source_tags, results, paths, report)
    tags = set(source_tags)
    for result in results:
        tags.update(result.tags)
    report.tags_found = sorted(tags)
    _check_orphans(tags, report, broken)
    _check_features(report)
    return report
