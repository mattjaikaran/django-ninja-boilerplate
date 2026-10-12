"""Playwright evidence: tags in e2e sources and results in the JSON report.

Pure Python on purpose. Playwright JSON strips the leading ``@`` from
``specs[].tags``; both forms are accepted, plus tags written inline in
suite and test titles.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from .spec_models import (
    BARE_TAG,
    E2E_GLOBS,
    FAILED,
    INLINE_TAG,
    PASSED,
    SKIPPED,
    STEP_SOURCE,
    STEP_TITLE,
    E2eResult,
    Issue,
)


def _inline_tags(text: str) -> set[str]:
    return set(INLINE_TAG.findall(text))


def scan_sources(e2e_dir: Path) -> dict[str, set[str]]:
    """Map each tag written in the e2e sources to the files that carry it."""
    index: dict[str, set[str]] = {}
    if not e2e_dir.is_dir():
        return index
    files: set[Path] = set()
    for pattern in E2E_GLOBS:
        files.update(p for p in e2e_dir.glob(pattern) if "node_modules" not in p.parts)
    for path in sorted(files):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(e2e_dir).as_posix()
        for tag in _inline_tags(text) | set(STEP_SOURCE.findall(text)):
            index.setdefault(tag, set()).add(rel)
    return index


def _test_outcome(test: Mapping[str, object]) -> str:
    status = test.get("status")
    if status == "expected":
        return PASSED
    if status == "skipped":
        return SKIPPED
    raw_results = test.get("results")
    results = [
        r.get("status")
        for r in (raw_results if isinstance(raw_results, list) else [])
        if isinstance(r, dict)
    ]
    if results and all(r == "passed" for r in results):
        return PASSED
    if results and all(r == "skipped" for r in results):
        return SKIPPED
    return FAILED


def _collect_steps(steps: object, out: dict[str, str]) -> None:
    """Record each `J-NNN-S<n>` step title; a failure in any attempt wins."""
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        title = step.get("title")
        match = STEP_TITLE.match(title) if isinstance(title, str) else None
        if match:
            outcome = FAILED if step.get("error") else PASSED
            if out.get(match.group(1)) != FAILED:
                out[match.group(1)] = outcome
        _collect_steps(step.get("steps"), out)


def _step_outcomes(tests: Sequence[Mapping[str, object]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for test in tests:
        raw_results = test.get("results")
        for result in raw_results if isinstance(raw_results, list) else []:
            if isinstance(result, dict):
                _collect_steps(result.get("steps"), out)
    return out


def _spec_result(
    spec: Mapping[str, object], inherited: set[str], file: str
) -> E2eResult:
    raw_title = spec.get("title")
    title = raw_title if isinstance(raw_title, str) else ""
    tags = inherited | _inline_tags(title)
    raw_tags = spec.get("tags")
    for tag in raw_tags if isinstance(raw_tags, list) else []:
        match = BARE_TAG.match(tag.strip()) if isinstance(tag, str) else None
        if match:
            tags.add(match.group(1))
    raw_tests = spec.get("tests")
    tests = [
        t
        for t in (raw_tests if isinstance(raw_tests, list) else [])
        if isinstance(t, dict)
    ]
    outcomes = [_test_outcome(t) for t in tests]
    step_outcomes = _step_outcomes(tests)
    tags.update(step_outcomes)
    ran = [o for o in outcomes if o != SKIPPED]
    if not ran:
        outcome = SKIPPED
    elif all(o == PASSED for o in ran):
        outcome = PASSED
    else:
        outcome = FAILED
    spec_file = spec.get("file")
    return E2eResult(
        title,
        spec_file if isinstance(spec_file, str) else file,
        frozenset(tags),
        outcome,
        step_outcomes,
    )


def _walk_suites(
    suites: object, inherited: set[str], file: str, out: list[E2eResult]
) -> None:
    for suite in suites if isinstance(suites, list) else []:
        if not isinstance(suite, dict):
            continue
        title = suite.get("title")
        tags = inherited | _inline_tags(title if isinstance(title, str) else "")
        suite_file = suite.get("file")
        here = suite_file if isinstance(suite_file, str) else file
        specs = suite.get("specs")
        for spec in specs if isinstance(specs, list) else []:
            if isinstance(spec, dict):
                out.append(_spec_result(spec, tags, here))
        _walk_suites(suite.get("suites"), tags, here, out)


def load_results(path: Path, warnings: list[Issue]) -> list[E2eResult]:
    """Parse the Playwright JSON report. A missing report yields no results."""
    if not path.is_file():
        return []
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        warnings.append(
            Issue(
                "bad_report",
                f"cannot read the Playwright JSON report: {exc}",
                path=str(path),
            )
        )
        return []
    results: list[E2eResult] = []
    if isinstance(raw, dict):
        _walk_suites(raw.get("suites"), set(), "", results)
    return results
