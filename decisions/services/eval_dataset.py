"""Load and validate labelled datasets for decision evals.

Three input shapes are accepted:

* A JSON file with ``name``, ``questions``, and ``cases`` (the original
  ``data/eval`` format).
* A JSONL file with one case per line. Each line has ``state`` and
  ``expected``, and optionally ``id``, ``split``, ``difficulty``, and its own
  ``questions``. Shared question definitions come from ``questions_path`` or
  a sibling ``questions.json``. Use this for reviewed production traffic.
* A benchmark domain directory with ``questions.json`` and ``cases.jsonl``.

``choice`` answers are correct when the label matches. ``noul`` answers are
correct when the yes probability (or boolean) lands on the expected side of
0.5. ``score`` questions are rejected before any provider call: CLM returns an
anchor index and Laya uses another scale, so one rule would mark a provider
wrong for its scale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.exceptions import ValidationError

#: Question types the eval can score.
SCORABLE_TYPES = frozenset({"choice", "noul"})

#: Benchmark shipped with the app: one directory per domain.
BENCHMARK_DIR = Path(__file__).resolve().parents[1] / "data" / "benchmark"


@dataclass(frozen=True, slots=True)
class EvalCase:
    """One labelled case, with the questions it asks."""

    case_id: str
    dataset: str
    split: str
    state: dict[str, Any]
    questions: dict[str, dict[str, Any]]
    expected: dict[str, Any]


def is_correct(question: dict[str, Any], answer: Any, expected: Any) -> bool:
    """Return whether *answer* matches *expected* for *question*'s type."""
    qtype = question.get("type")
    if qtype == "choice":
        return bool(answer == expected)
    if qtype == "noul":
        said_yes = answer if isinstance(answer, bool) else float(answer) >= 0.5
        return said_yes is bool(expected)
    raise ValidationError(unsupported_type_message(qtype))


def unsupported_type_message(qtype: Any) -> str:
    """Return the error text for a question type the eval cannot score."""
    if qtype == "score":
        return (
            "Score questions are not supported in eval datasets: providers "
            "report scores on different scales."
        )
    return f"Unsupported question type '{qtype}' in eval dataset."


def validate_questions(questions: dict[str, Any]) -> None:
    """Reject question types the eval cannot score.

    Raises:
        ValidationError: If any question is not ``choice`` or ``noul``.
    """
    for key, question in questions.items():
        qtype = question.get("type") if isinstance(question, dict) else None
        if qtype not in SCORABLE_TYPES:
            raise ValidationError(
                f"Question '{key}': {unsupported_type_message(qtype)}"
            )


def _case(
    raw: dict[str, Any], index: int, dataset: str, questions: dict[str, Any]
) -> EvalCase:
    """Build one :class:`EvalCase`, validating its labels against *questions*."""
    case_id = str(raw.get("id") or f"{dataset}-{index + 1}")
    asked_from = raw.get("questions") or questions
    expected = raw.get("expected")
    if not isinstance(expected, dict) or not expected:
        raise ValidationError(f"Case '{case_id}' has no expected labels.")
    if not isinstance(raw.get("state"), dict):
        raise ValidationError(f"Case '{case_id}' has no state object.")
    unknown = set(expected) - set(asked_from)
    if unknown:
        raise ValidationError(
            f"Case '{case_id}': expected labels for unknown questions: {sorted(unknown)}."
        )
    asked = {key: asked_from[key] for key in expected}
    validate_questions(asked)
    for key, label in expected.items():
        criteria = asked[key].get("criteria")
        if asked[key]["type"] == "choice" and criteria and label not in criteria:
            raise ValidationError(
                f"Case '{case_id}': label '{label}' is not a '{key}' option."
            )
    return EvalCase(
        case_id=case_id,
        dataset=dataset,
        split=str(raw.get("split") or ""),
        state=raw["state"],
        questions=asked,
        expected=expected,
    )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Cannot read {path}: {exc}") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{path}:{number}: invalid JSON: {exc}") from exc
    return rows


def load_cases(
    path: Path,
    questions_path: Path | None = None,
    split: str | None = None,
) -> list[EvalCase]:
    """Load labelled cases from a JSON file, a JSONL file, or a domain directory.

    Args:
        path: Dataset path.
        questions_path: Shared question definitions for a JSONL file.
        split: Keep only cases with this ``split`` value.

    Raises:
        ValidationError: If the file is unreadable, a case is malformed, a
            question type cannot be scored, or no case remains.
    """
    if path.is_dir():
        questions_path = questions_path or path / "questions.json"
        path = path / "cases.jsonl"
    if not path.is_file():
        raise ValidationError(f"Dataset not found: {path}")
    if path.suffix == ".jsonl":
        if questions_path is None and (path.parent / "questions.json").is_file():
            questions_path = path.parent / "questions.json"
        header = _read_json(questions_path) if questions_path else {}
        raw_cases = _read_jsonl(path)
        default_name = path.parent.name if path.name == "cases.jsonl" else path.stem
    else:
        header = _read_json(path)
        raw_cases = header.get("cases") or []
        default_name = path.stem
    questions = header.get("questions") or {}
    validate_questions(questions)
    name = header.get("name") or default_name
    cases = [_case(raw, i, name, questions) for i, raw in enumerate(raw_cases)]
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValidationError(f"{path}: case ids are not unique.")
    if split:
        cases = [case for case in cases if case.split == split]
    if not cases:
        raise ValidationError(f"The eval dataset {path} has no cases.")
    return cases


def benchmark_domains() -> list[Path]:
    """Return every bundled benchmark domain directory, sorted by name."""
    return sorted(p for p in BENCHMARK_DIR.iterdir() if (p / "cases.jsonl").is_file())


def check_question_keys(cases: list[EvalCase]) -> None:
    """Reject one question key with two different definitions.

    Per-question reports and thresholds are keyed by question name, so a key
    must mean the same thing in every dataset of one run.
    """
    seen: dict[str, dict[str, Any]] = {}
    for case in cases:
        for key, question in case.questions.items():
            if seen.setdefault(key, question) != question:
                raise ValidationError(
                    f"Question '{key}' has two different definitions in this run."
                )
