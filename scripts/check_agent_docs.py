#!/usr/bin/env python3
"""AGENT-DOCS gate: the agent instructions exist, stay short and stay honest.

Checks:
  1. ``AGENTS.md`` exists and is at most ``MAX_LINES`` lines.
  2. Every relative Markdown link in ``AGENTS.md`` resolves to a repo path.
  3. Every ``just <recipe>`` in ``AGENTS.md`` names a recipe in the justfile.
  4. Every repo path in backticks in ``AGENTS.md`` exists.
  5. Each ``.agents/skills/<name>/SKILL.md`` has ``name`` (matching the
     directory) and ``description`` frontmatter, ``SKILLS.md`` lists it, and
     no other directory tracks a skill.
  6. ``CLAUDE.md``, when present, is the single line ``@AGENTS.md``.
  7. ``.cursorrules`` and tracked ``.cursor/`` rules are gone: Cursor reads
     ``AGENTS.md``.

Usage:
    python3 scripts/check_agent_docs.py
    python3 scripts/check_agent_docs.py --agents path/to/AGENTS.md
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_NAME = "AGENTS.md"
SKILLS_DIR = Path(".agents/skills")
SKILLS_INDEX = "SKILLS.md"
CLAUDE_NAME = "CLAUDE.md"
JUSTFILE = "justfile"
MAX_LINES = 200

# Backtick paths under these prefixes must exist. Anything else (a module name,
# a setting, a command) is prose, not a path.
PATH_PREFIXES = (
    "scripts/",
    "docs/",
    "tests/",
    "tasks/",
    ".agents/",
    ".omp/",
    ".context/",
    ".github/",
)
FILE_SUFFIXES = (".md", ".py", ".json", ".yml", ".yaml", ".toml", ".sh", ".mdc")

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
JUST_CALL = re.compile(r"^just\s+([a-z][a-z0-9-]*)")
RECIPE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)[^:=]*:(?!=)", re.MULTILINE)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:")


def relative_links(text: str) -> list[str]:
    """Return the link targets that point inside the repository."""
    targets = []
    for target in LINK.findall(text):
        if target.startswith("#") or SCHEME.match(target):
            continue
        targets.append(target.split("#", 1)[0])
    return [target for target in targets if target]


def just_calls(text: str) -> list[str]:
    """Return the ``just <recipe>`` calls written as inline code."""
    names = []
    for span in CODE_SPAN.findall(text):
        span = span.strip()
        if span.startswith(("just ", "just\n")):
            match = JUST_CALL.match(" ".join(span.split()))
            if match:
                names.append(match.group(1))
    return names


def path_tokens(text: str) -> list[str]:
    """Return backtick tokens that look like a repository path."""
    tokens = []
    for span in CODE_SPAN.findall(text):
        token = span.split()[0] if span.split() else ""
        token = token.rstrip(".,;:")
        if any(marker in token for marker in "*<>"):
            continue
        if not token.startswith(PATH_PREFIXES):
            continue
        if not (token.endswith(FILE_SUFFIXES) or token.endswith("/")):
            continue
        tokens.append(token)
    return tokens


def recipe_names(justfile: Path) -> set[str]:
    """Return the recipe names a justfile defines."""
    return set(RECIPE.findall(justfile.read_text(encoding="utf-8")))


def tracked_skill_files(root: Path) -> list[str]:
    """Return the tracked SKILL.md paths, via git when it is available."""
    result = subprocess.run(
        ["git", "ls-files", "*SKILL.md"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return [str(path.relative_to(root)) for path in root.glob("**/SKILL.md")]
    return [line for line in result.stdout.splitlines() if line]


def frontmatter(text: str) -> dict[str, str]:
    """Return the simple ``key: value`` pairs of a YAML frontmatter block."""
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    key = ""
    for line in match.group(1).splitlines():
        if line.startswith((" ", "\t")) and key:
            fields[key] += " " + line.strip()
        elif ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().lstrip(">").strip()
    return fields


def check_agents(root: Path, agents: Path, errors: list[str]) -> None:
    """Check the AGENTS.md file itself."""
    if not agents.is_file():
        errors.append(f"{agents}: missing; it is the canonical agent guidance")
        return

    text = agents.read_text(encoding="utf-8")
    lines = text.count("\n") + (0 if text.endswith("\n") else 1)
    if lines > MAX_LINES:
        errors.append(
            f"{agents.name}: {lines} lines, over the {MAX_LINES}-line cap; "
            "move procedure into .agents/skills/ or docs/"
        )

    for target in relative_links(text):
        if not (root / target).exists():
            errors.append(f"{agents.name}: link target does not resolve: {target}")

    recipes: set[str] | None = None
    justfile = root / JUSTFILE
    if justfile.is_file():
        recipes = recipe_names(justfile)
    for name in sorted(set(just_calls(text))):
        if recipes is not None and name not in recipes:
            errors.append(f"{agents.name}: `just {name}` is not a justfile recipe")

    for token in sorted(set(path_tokens(text))):
        if not (root / token).exists():
            errors.append(f"{agents.name}: cited path does not exist: {token}")


def check_skills(root: Path, errors: list[str]) -> None:
    """Check the skills location, frontmatter and index."""
    skills_dir = root / SKILLS_DIR
    index = root / SKILLS_INDEX
    if not skills_dir.is_dir():
        errors.append(f"{SKILLS_DIR}: missing; skills live here")
        return
    if not index.is_file():
        errors.append(f"{SKILLS_INDEX}: missing; it indexes {SKILLS_DIR}")
        return
    index_text = index.read_text(encoding="utf-8")

    for path in sorted(skills_dir.glob("*/SKILL.md")):
        name = path.parent.name
        fields = frontmatter(path.read_text(encoding="utf-8"))
        if fields.get("name") != name:
            errors.append(f"{path}: frontmatter name must match the directory ({name})")
        if not fields.get("description"):
            errors.append(f"{path}: frontmatter needs a description")
        if f"{SKILLS_DIR / name / 'SKILL.md'}" not in index_text:
            errors.append(f"{SKILLS_INDEX}: no row for the {name} skill")

    for tracked in tracked_skill_files(root):
        if not tracked.startswith((str(SKILLS_DIR) + "/", ".omp/skills/")):
            errors.append(
                f"{tracked}: skills live in {SKILLS_DIR}/ only, not a second location"
            )


def check_harness_files(root: Path, errors: list[str]) -> None:
    """Check the files that would restate AGENTS.md."""
    claude = root / CLAUDE_NAME
    if claude.is_file() and claude.read_text(encoding="utf-8").strip() != "@AGENTS.md":
        errors.append(f"{CLAUDE_NAME}: must contain only @AGENTS.md")

    if (root / ".cursorrules").exists():
        errors.append(".cursorrules: fold it into AGENTS.md and delete it")
    for path in sorted((root / ".cursor").rglob("*.mdc")):
        errors.append(f"{path.relative_to(root)}: Cursor reads AGENTS.md; delete it")


def main() -> int:
    """Run every check; return 1 when one fails."""
    parser = argparse.ArgumentParser(description=__doc__ or "Check agent docs")
    parser.add_argument("--agents", default=AGENTS_NAME, help="path to AGENTS.md")
    parser.add_argument(
        "--root", default=str(PROJECT_ROOT), help="repository root to check"
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors: list[str] = []
    check_agents(root, root / args.agents, errors)
    check_skills(root, errors)
    check_harness_files(root, errors)

    if errors:
        print("AGENT-DOCS gate failed:")
        for error in errors:
            print(f"  {error}")
        return 1

    print(f"AGENT-DOCS passed ({args.agents}, {SKILLS_DIR})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
