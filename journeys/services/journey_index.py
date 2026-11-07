"""The journey index: one row per journey, with its tests and endpoints.

Reads the journeys table of ``docs/product/journeys.md`` (the plan: ID,
journey, stories, backend surface, tests) and checks which test files exist.
The staff page shows the result in plain words; nothing here is a sync rule,
so the JOURNEYS gate ignores it.

Pure Python on purpose, like the rest of ``journeys.services``: no Django.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .spec_models import FAILED, PASSED, SKIPPED, E2eResult, SpecPaths

INDEX_ID = re.compile(r"^J-(\d{2,3})$")
CODE_SPAN = re.compile(r"`([^`]+)`")
METHODS = "GET|POST|PUT|PATCH|DELETE"
ENDPOINT = re.compile(rf"^((?:{METHODS})(?:/(?:{METHODS}))*)\s+(/\S*)")
TEST_FILE = re.compile(r"^(?P<path>[\w./-]+\.py)(?:::\S+)?$")
SPEC_FILE = re.compile(r"^[\w./-]+\.(?:spec|test)\.(?:ts|js)$")

# Status of a journey, from the test files that exist.
TESTED = "tested"
BACKEND_ONLY = "backend_only"
BROWSER_ONLY = "browser_only"
PLANNED = "planned"
STATUS_LABELS = {
    TESTED: "Backend and browser tests",
    BACKEND_ONLY: "Backend test only",
    BROWSER_ONLY: "Browser test only",
    PLANNED: "Not started",
}
STATUS_ORDER = (TESTED, BACKEND_ONLY, BROWSER_ONLY, PLANNED)

NOTE_LIMIT = 160
# The table shows this many endpoints per journey; the rest are counted.
ENDPOINTS_SHOWN = 6
# String literals a smoke test passes to its client: "/api/x", f"/api/x/{id}".
API_LITERAL = re.compile(r"""f?["'](/api/[\w\-./{}@]+)["']""")
PLACEHOLDER = re.compile(r"\{[^}]*\}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f-]{4,}-[0-9a-f-]+")


@dataclass(frozen=True)
class FileRef:
    """A test file the plan names, and whether it exists on disk."""

    path: str
    exists: bool


@dataclass
class IndexedJourney:
    id: str
    title: str
    stories: list[str]
    surface: str
    endpoints: list[str]
    # Where the endpoints come from: the plan's table, the smoke tests, or both.
    endpoints_source: str
    smoke_tests: list[FileRef]
    browser_test: FileRef | None
    browser_note: str
    last_run: str
    status: str
    spec_status: str = ""
    # Set by the view when the feature spec has a journey with this ID.
    detail_url: str = ""

    @property
    def status_label(self) -> str:
        return STATUS_LABELS[self.status]

    @property
    def shown_endpoints(self) -> list[str]:
        return self.endpoints[:ENDPOINTS_SHOWN]

    @property
    def hidden_endpoint_count(self) -> int:
        return max(len(self.endpoints) - ENDPOINTS_SHOWN, 0)

    @property
    def last_run_label(self) -> str:
        return self.last_run.replace("_", " ")


@dataclass
class JourneyIndex:
    path: Path
    found: bool
    journeys: list[IndexedJourney] = field(default_factory=list)

    @property
    def counts(self) -> list[tuple[str, str, int]]:
        """``(status, label, count)`` for every status, in display order."""
        return [
            (s, STATUS_LABELS[s], sum(1 for j in self.journeys if j.status == s))
            for s in STATUS_ORDER
        ]


def find_index_file(paths: SpecPaths, base_dir: Path) -> Path:
    """The index file: ``JOURNEYS_INDEX_FILE``, else the first default that exists."""
    if paths.index_file is not None:
        return paths.index_file
    candidates = [
        paths.spec_dir / "journeys.md",
        base_dir.resolve().parent / "docs" / "product" / "journeys.md",
    ]
    return next((c for c in candidates if c.is_file()), candidates[0])


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_rule(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c)


def _plain(text: str) -> str:
    """The cell without code ticks and doubled spaces."""
    return re.sub(r"\s+", " ", text.replace("`", "")).strip()


def _short(text: str) -> str:
    text = _plain(text)
    if len(text) <= NOTE_LIMIT:
        return text
    return text[: NOTE_LIMIT - 1].rsplit(" ", 1)[0] + "…"


def _column(headers: list[str], *needles: str) -> int | None:
    for needle in needles:
        for i, header in enumerate(headers):
            if needle in header:
                return i
    return None


def parse_rows(text: str) -> list[dict[str, str]]:
    """Rows of the journeys table, keyed by ``id``, ``title``, ``stories``,
    ``surface``, ``smoke`` and ``browser``. Returns ``[]`` without a table.
    """
    lines = text.splitlines()
    for start, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        headers = [h.lower() for h in _cells(line)]
        if not headers or headers[0] != "id":
            continue
        cols = {
            "id": 0,
            "title": _column(headers, "journey", "title"),
            "stories": _column(headers, "stor"),
            "surface": _column(headers, "backend surface", "endpoint", "surface"),
            "smoke": _column(headers, "smoke"),
            "browser": _column(headers, "playwright", "browser", "e2e"),
        }
        if cols["title"] is None:
            continue
        rows: list[dict[str, str]] = []
        for row_line in lines[start + 1 :]:
            if not row_line.lstrip().startswith("|"):
                break
            cells = _cells(row_line)
            if _is_rule(cells) or not INDEX_ID.match(cells[0].strip("` ")):
                continue
            rows.append(
                {
                    key: cells[i] if i is not None and i < len(cells) else ""
                    for key, i in cols.items()
                }
            )
        return rows
    return []


def _spans(cell: str) -> list[str]:
    return [span.strip() for span in CODE_SPAN.findall(cell)]


def endpoints_of(cell: str) -> list[str]:
    """``GET /api/x`` style spans of a cell, in order, without repeats."""
    found: list[str] = []
    for span in _spans(cell):
        match = ENDPOINT.match(span)
        if match and (text := f"{match.group(1)} {match.group(2)}") not in found:
            found.append(text)
    return found


def _smoke_paths(row: Mapping[str, str]) -> list[str]:
    """Test files the plan names for the backend, from the smoke and surface cells."""
    out: list[str] = []
    for cell in (row["smoke"], row["surface"], row["browser"]):
        for span in _spans(cell):
            match = TEST_FILE.match(span)
            if match and "test_" in match.group("path"):
                if match.group("path") not in out:
                    out.append(match.group("path"))
    return out


def _smoke_by_name(
    journey_id: str, smoke_dir: Path | None, base_dir: Path
) -> list[str]:
    """Smoke files named ``test_j<number>_*.py`` when the plan names none."""
    if smoke_dir is None or not smoke_dir.is_dir():
        return []
    digits = journey_id[2:]
    number = int(digits)
    names = {f"{digits}", f"{number:02d}", f"{number:03d}"}
    found: list[str] = []
    for name in sorted(names):
        for file in sorted(smoke_dir.glob(f"test_j{name}_*.py")):
            rel = _relative(file, base_dir)
            if rel not in found:
                found.append(rel)
    return found


def _relative(path: Path, base_dir: Path) -> str:
    try:
        return path.resolve().relative_to(base_dir.resolve()).as_posix()
    except ValueError:
        return str(path)


def _dedicated(ref: FileRef, journey_id: str) -> bool:
    """Whether the file is named for this journey (``test_j003_*.py``).

    A shared file such as ``test_smoke.py`` proves every journey, so its
    endpoints belong to none of them.
    """
    match = re.match(r"^test_j(\d+)_", Path(ref.path).name)
    return bool(match) and int(match.group(1)) == int(journey_id[2:])


def _normalized(path: str) -> str:
    """The path with every ``{placeholder}`` as ``{}``, for comparing the
    plan (``{key_id}``) with the code (``{key_id}``, ``{id}``, ``{new_id}``).
    """
    return re.sub(r"\{[^}]*\}", "{}", path)


def smoke_endpoints(files: Iterable[FileRef], base_dir: Path) -> list[str]:
    """API paths the smoke test files call, in order, without repeats."""
    root = base_dir.resolve()
    found: list[str] = []
    for ref in files:
        if not ref.exists:
            continue
        try:
            file = (base_dir / ref.path).resolve()
            file.relative_to(root)
            text = file.read_text(encoding="utf-8")
        except (OSError, ValueError):
            continue
        for literal in API_LITERAL.findall(text):
            path = PLACEHOLDER.sub("{id}", literal)
            if path not in found:
                found.append(path)
    return found


def _browser_path(cell: str) -> str:
    return next((s for s in _spans(cell) if SPEC_FILE.match(s)), "")


def _browser_exists(spec: str, paths: SpecPaths) -> bool:
    """The spec path in the plan is relative to the frontend (``e2e/j07.spec.ts``)."""
    return (paths.e2e_dir.parent / spec).is_file() or (
        paths.e2e_dir / Path(spec).name
    ).is_file()


def _last_run(spec: str, results: Iterable[E2eResult]) -> str:
    """``passed``, ``failed``, ``skipped`` or ``no_result`` from the JSON report."""
    name = Path(spec).name
    outcomes = {r.outcome for r in results if Path(r.file).name == name}
    if not outcomes:
        return "no_result"
    if FAILED in outcomes:
        return FAILED
    return PASSED if outcomes == {PASSED} else SKIPPED


def _status(has_backend: bool, has_browser: bool) -> str:
    if has_backend and has_browser:
        return TESTED
    if has_backend:
        return BACKEND_ONLY
    if has_browser:
        return BROWSER_ONLY
    return PLANNED


def build_index(
    paths: SpecPaths,
    base_dir: Path,
    results: Iterable[E2eResult] = (),
    spec_statuses: Mapping[str, str] | None = None,
) -> JourneyIndex:
    """Read the index file and check the test files it names.

    ``spec_statuses`` maps a journey ID to its status in the feature spec
    (``draft``, ``building``, ``done``), for the journeys that have one.
    """
    index_file = find_index_file(paths, base_dir)
    if not index_file.is_file():
        return JourneyIndex(index_file, found=False)
    rows = parse_rows(index_file.read_text(encoding="utf-8"))
    statuses = spec_statuses or {}
    results = list(results)
    journeys: list[IndexedJourney] = []
    for row in rows:
        journey_id = row["id"].strip("` ")
        named = _smoke_paths(row) or _smoke_by_name(
            journey_id, paths.smoke_dir, base_dir
        )
        smoke = [FileRef(p, (base_dir / p).is_file()) for p in named]
        planned = endpoints_of(row["surface"])
        plan_paths = {_normalized(e.split(" ", 1)[1].split("?")[0]) for e in planned}
        dedicated = [ref for ref in smoke if _dedicated(ref, journey_id)]
        called = [
            c
            for c in smoke_endpoints(dedicated, base_dir)
            if _normalized(c) not in plan_paths
        ]
        spec = _browser_path(row["browser"])
        browser = FileRef(spec, _browser_exists(spec, paths)) if spec else None
        journeys.append(
            IndexedJourney(
                id=journey_id,
                title=_plain(row["title"]),
                stories=[
                    s.strip()
                    for s in re.split(r"[,;]", _plain(row["stories"]))
                    if s.strip()
                ],
                surface=_short(row["surface"]),
                endpoints=[*planned, *called],
                endpoints_source=(
                    "the plan and the smoke test"
                    if planned and called
                    else "the plan"
                    if planned
                    else "the smoke test"
                ),
                smoke_tests=smoke,
                browser_test=browser,
                browser_note=_short(CODE_SPAN.sub("", row["browser"]).lstrip(": ")),
                last_run=_last_run(spec, results) if browser and browser.exists else "",
                status=_status(
                    any(f.exists for f in smoke), bool(browser and browser.exists)
                ),
                spec_status=statuses.get(journey_id, ""),
            )
        )
    return JourneyIndex(index_file, found=True, journeys=journeys)
