#!/usr/bin/env python3
"""Validate, list, claim, and show work tickets in docs/tickets/.

A ticket is ``docs/tickets/T-NNN-slug.md``: YAML frontmatter plus fixed body
sections. In-flight state lives in git, not in the file: a remote branch
``agent/T-NNN-*`` means the ticket is claimed. See docs/tickets/README.md.

Usage:
    python scripts/tickets.py check                 # gate: exit 1 on any error
    python scripts/tickets.py next [--tier small]   # list claimable tickets
    python scripts/tickets.py claim T-001           # atomic claim via git push
    python scripts/tickets.py claim T-001 --dry-run # print the git commands
    python scripts/tickets.py show T-001            # ticket plus claimability

Environment:
    TICKETS_DIR  ticket directory (default: <repo>/docs/tickets)

Exit: 0 = success, 1 = validation errors or failed claim, 2 = usage or git error
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TICKETS_DIR = PROJECT_ROOT / "docs" / "tickets"
SKIP_FILES = {"README.md", "TEMPLATE.md"}

STATUSES = ("draft", "ready", "blocked", "done")
TIERS = ("small", "large")
LIST_KEYS = ("depends_on", "owns", "shared", "journeys", "features")
STR_KEYS = ("id", "title", "status", "tier", "branch")
REQUIRED_KEYS = STR_KEYS + LIST_KEYS
REQUIRED_SECTIONS = ("Context", "Change", "Do not", "Verify", "Done when")

TICKET_ID_RE = re.compile(r"^T-\d{3}$")
FILE_PREFIX_RE = re.compile(r"^(T-\d{3})(?:-|\.md$)")
LIST_ITEM_RE = {
    "depends_on": TICKET_ID_RE,
    "journeys": re.compile(r"^J-\d{3}$"),
    "features": re.compile(r"^F-\d{3}$"),
}
BRANCH_ID_RE = re.compile(r"^agent/(T-\d{3})-")
HEADING_RE = re.compile(r"^## +(.+?) *$", re.MULTILINE)
FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
GLOB_CHARS = "*?["


@dataclass
class Ticket:
    path: Path
    id: str
    title: str
    status: str
    tier: str
    branch: str
    depends_on: list[str]
    owns: list[str]
    shared: list[str]
    journeys: list[str]
    features: list[str]
    sections: dict[str, str] = field(default_factory=dict)

    @property
    def paths(self) -> list[str]:
        """Every path the ticket may touch: owned files plus hot files."""
        return self.owns + self.shared


@dataclass
class Board:
    tickets: dict[str, Ticket] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def tickets_dir() -> Path:
    """Return the ticket directory, honoring the TICKETS_DIR override."""
    override = os.environ.get("TICKETS_DIR")
    return Path(override) if override else DEFAULT_TICKETS_DIR


def ticket_files(directory: Path) -> list[Path]:
    """Return ticket files, skipping README.md and TEMPLATE.md."""
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.glob("T-*.md") if path.name not in SKIP_FILES
    )


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str, str]:
    """Split a Markdown file into (frontmatter, body, error)."""
    if not text.startswith("---\n"):
        return None, text, "missing YAML frontmatter (file must start with '---')"
    end = text.find("\n---", 4)
    if end == -1:
        return None, text, "unterminated YAML frontmatter (no closing '---')"
    try:
        data = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        return None, text, f"invalid YAML frontmatter: {exc}"
    if not isinstance(data, dict):
        return None, text, "frontmatter must be a YAML mapping"
    body = text[end + 4 :].split("\n", 1)[1] if "\n" in text[end + 4 :] else ""
    return data, body, ""


def split_sections(body: str) -> dict[str, str]:
    """Map each ``## Heading`` to the text under it."""
    matches = list(HEADING_RE.finditer(body))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[match.group(1)] = body[match.end() : stop]
    return sections


def validate_keys(data: dict[str, Any], where: str) -> list[str]:
    """Check frontmatter keys, types, enums, and list item formats."""
    errors: list[str] = []
    missing = [key for key in REQUIRED_KEYS if key not in data]
    unknown = sorted(set(data) - set(REQUIRED_KEYS))
    if missing:
        errors.append(f"{where}: missing frontmatter keys: {', '.join(missing)}")
    if unknown:
        errors.append(f"{where}: unknown frontmatter keys: {', '.join(unknown)}")
    for key in STR_KEYS:
        if key in data and not isinstance(data[key], str):
            errors.append(f"{where}: '{key}' must be a string")
    for key in LIST_KEYS:
        value = data.get(key)
        if key in data and not (
            isinstance(value, list) and all(isinstance(v, str) for v in value)
        ):
            errors.append(f"{where}: '{key}' must be a list of strings")
            continue
        pattern = LIST_ITEM_RE.get(key)
        for item in value or []:
            if pattern and not pattern.match(item):
                errors.append(f"{where}: '{key}' item '{item}' has a bad format")
    if data.get("status") not in STATUSES:
        errors.append(
            f"{where}: status '{data.get('status')}' not in {'|'.join(STATUSES)}"
        )
    if data.get("tier") not in TIERS:
        errors.append(f"{where}: tier '{data.get('tier')}' not in {'|'.join(TIERS)}")
    return errors


def validate_ticket(ticket: Ticket, where: str) -> list[str]:
    """Check id, branch, body sections, and the small+ready requirements."""
    errors: list[str] = []
    if not TICKET_ID_RE.match(ticket.id):
        errors.append(f"{where}: id '{ticket.id}' must match T-NNN")
    prefix = FILE_PREFIX_RE.match(ticket.path.name)
    if not prefix or prefix.group(1) != ticket.id:
        errors.append(
            f"{where}: id '{ticket.id}' does not match the file name prefix "
            f"(expected {ticket.id}-slug.md)"
        )
    if ticket.branch and not ticket.branch.startswith(f"agent/{ticket.id}-"):
        errors.append(
            f"{where}: branch '{ticket.branch}' must start with 'agent/{ticket.id}-'"
        )
    if ticket.id in ticket.depends_on:
        errors.append(f"{where}: ticket depends on itself")
    missing = [name for name in REQUIRED_SECTIONS if name not in ticket.sections]
    if missing:
        errors.append(
            f"{where}: missing body sections: "
            + ", ".join(f"## {name}" for name in missing)
        )
    if ticket.tier == "small" and ticket.status == "ready":
        errors.extend(validate_small_ready(ticket, where))
    return errors


def validate_small_ready(ticket: Ticket, where: str) -> list[str]:
    """A ready small ticket must be executable with no exploration."""
    errors: list[str] = []
    if not ticket.owns:
        errors.append(f"{where}: tier small + status ready requires non-empty owns")
    verify = ticket.sections.get("Verify", "")
    if not any(block.strip() for block in FENCE_RE.findall(verify)):
        errors.append(
            f"{where}: tier small + status ready requires a fenced command "
            "block under ## Verify"
        )
    if not ticket.branch:
        errors.append(
            f"{where}: tier small + status ready requires a branch "
            f"'agent/{ticket.id}-<slug>'"
        )
    return errors


def load_ticket(path: Path) -> tuple[Ticket | None, list[str]]:
    """Parse and validate one ticket file."""
    where = display(path)
    data, body, error = split_frontmatter(path.read_text(encoding="utf-8"))
    if data is None:
        return None, [f"{where}: {error}"]
    errors = validate_keys(data, where)
    if errors:
        return None, errors
    ticket = Ticket(
        path=path,
        sections=split_sections(body),
        **{key: data[key] for key in REQUIRED_KEYS},
    )
    return ticket, validate_ticket(ticket, where)


def load_board(directory: Path) -> Board:
    """Load every ticket and run the per-ticket and cross-ticket checks."""
    board = Board()
    for path in ticket_files(directory):
        ticket, errors = load_ticket(path)
        board.errors.extend(errors)
        if ticket is None:
            continue
        if ticket.id in board.tickets:
            other = display(board.tickets[ticket.id].path)
            board.errors.append(
                f"{display(path)}: duplicate id {ticket.id} (also in {other})"
            )
            continue
        board.tickets[ticket.id] = ticket
    board.errors.extend(check_dependencies(board.tickets))
    board.errors.extend(check_collisions(board.tickets))
    return board


def display(path: Path) -> str:
    """Return *path* relative to the repo root when possible."""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Dependencies and collisions
# ---------------------------------------------------------------------------


def check_dependencies(tickets: dict[str, Ticket]) -> list[str]:
    """Report unknown dependencies and dependency cycles."""
    errors: list[str] = []
    for ticket in tickets.values():
        for dep in ticket.depends_on:
            if dep not in tickets:
                errors.append(
                    f"{display(ticket.path)}: depends_on {dep} does not exist"
                )
    errors.extend(
        f"dependency cycle: {' -> '.join(cycle)}" for cycle in find_cycles(tickets)
    )
    return errors


def find_cycles(tickets: dict[str, Ticket]) -> list[list[str]]:
    """Return one representative path for each dependency cycle found."""
    state: dict[str, int] = {}  # 1 = on stack, 2 = finished
    cycles: list[list[str]] = []

    def visit(node: str, stack: list[str]) -> None:
        state[node] = 1
        stack.append(node)
        for dep in tickets[node].depends_on:
            if dep not in tickets:
                continue
            if state.get(dep) == 1:
                cycles.append([*stack[stack.index(dep) :], dep])
            elif dep not in state:
                visit(dep, stack)
        stack.pop()
        state[node] = 2

    for ticket_id in sorted(tickets):
        if ticket_id not in state:
            visit(ticket_id, [])
    return cycles


def ancestors(ticket_id: str, tickets: dict[str, Ticket]) -> set[str]:
    """Return every ticket reachable through depends_on from *ticket_id*."""
    seen: set[str] = set()
    pending = list(tickets[ticket_id].depends_on) if ticket_id in tickets else []
    while pending:
        dep = pending.pop()
        if dep in seen or dep not in tickets:
            continue
        seen.add(dep)
        pending.extend(tickets[dep].depends_on)
    return seen


def ordered(a: str, b: str, tickets: dict[str, Ticket]) -> bool:
    """Return True when a depends_on path links the two tickets."""
    return a in ancestors(b, tickets) or b in ancestors(a, tickets)


def static_prefix(pattern: str) -> str:
    """Return the part of a glob before its first wildcard character."""
    cut = min((pattern.find(c) for c in GLOB_CHARS if c in pattern), default=-1)
    return pattern if cut == -1 else pattern[:cut]


def normalize(entry: str) -> str:
    """Strip whitespace, a leading './', and a trailing '/'."""
    return entry.strip().removeprefix("./").rstrip("/")


def paths_overlap(a: str, b: str) -> bool:
    """Return True when two owns/shared entries can name the same file.

    Entries are repo-relative paths, directories (a trailing ``/`` is
    optional), or globs. The check is conservative: two globs overlap when
    one static prefix is a prefix of the other.
    """
    a, b = normalize(a), normalize(b)
    if not a or not b or a == b:
        return bool(a and b)
    if b.startswith(f"{a}/") or a.startswith(f"{b}/"):
        return True
    if fnmatch.fnmatchcase(a, b) or fnmatch.fnmatchcase(b, a):
        return True
    if any(c in a + b for c in GLOB_CHARS):
        pa, pb = static_prefix(a), static_prefix(b)
        return pa.startswith(pb) or pb.startswith(pa)
    return False


def overlaps(first: Ticket, second: Ticket) -> list[tuple[str, str]]:
    """Return every (first path, second path) pair that overlaps."""
    return [(a, b) for a in first.paths for b in second.paths if paths_overlap(a, b)]


def check_collisions(tickets: dict[str, Ticket]) -> list[str]:
    """Ready tickets with no depends_on path between them must not overlap."""
    ready = [tickets[key] for key in sorted(tickets) if tickets[key].status == "ready"]
    errors: list[str] = []
    for index, first in enumerate(ready):
        for second in ready[index + 1 :]:
            if ordered(first.id, second.id, tickets):
                continue
            pairs = overlaps(first, second)
            if pairs:
                detail = "; ".join(f"{a} <-> {b}" for a, b in pairs)
                errors.append(
                    f"collision: {first.id} and {second.id} are both ready, "
                    f"have no depends_on path, and overlap: {detail}"
                )
    return errors


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------


class GitError(RuntimeError):
    pass


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command with an argument list (no shell)."""
    # Argument list, no shell; callers pass fixed git subcommands and
    # validated ticket ids and branch names.
    # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result


def has_origin() -> bool:
    """Return True when the repo has an 'origin' remote."""
    return git("remote", "get-url", "origin", check=False).returncode == 0


def agent_branches() -> tuple[set[str], str]:
    """Return (agent/* branch names, source description).

    Uses the origin remote. Without a remote, falls back to local branches.
    """
    if has_origin():
        out = git("ls-remote", "--heads", "origin", "agent/*").stdout
        names = {
            line.split("refs/heads/", 1)[1]
            for line in out.splitlines()
            if "refs/heads/" in line
        }
        return names, "origin"
    out = git("for-each-ref", "--format=%(refname:short)", "refs/heads/agent/").stdout
    return {line.strip() for line in out.splitlines() if line.strip()}, "local"


def claimed_ids(branches: set[str]) -> set[str]:
    """Map agent/T-NNN-* branch names to ticket ids."""
    return {m.group(1) for b in branches if (m := BRANCH_ID_RE.match(b))}


# ---------------------------------------------------------------------------
# Claimability
# ---------------------------------------------------------------------------


def blockers(ticket: Ticket, board: Board, claimed: set[str]) -> list[str]:
    """Return the reasons *ticket* cannot be claimed now (empty = claimable)."""
    reasons: list[str] = []
    if ticket.status != "ready":
        reasons.append(f"status is '{ticket.status}', not 'ready'")
    if not ticket.branch:
        reasons.append("no branch set")
    pending = [
        dep
        for dep in ticket.depends_on
        if dep not in board.tickets or board.tickets[dep].status != "done"
    ]
    if pending:
        reasons.append(f"dependencies not done: {', '.join(pending)}")
    if ticket.id in claimed:
        reasons.append("already claimed (an agent/<id>-* branch exists)")
    for other_id in sorted(claimed - {ticket.id}):
        other = board.tickets.get(other_id)
        if other is None or other.status == "done":
            continue
        pairs = overlaps(ticket, other)
        if pairs:
            detail = ", ".join(f"{a} <-> {b}" for a, b in pairs)
            reasons.append(f"overlaps claimed {other_id}: {detail}")
    return reasons


def require_board() -> Board:
    """Load the board; exit 1 when it fails validation."""
    board = load_board(tickets_dir())
    if board.errors:
        print_errors(board.errors)
        print("Fix the errors above (run 'tickets.py check').", file=sys.stderr)
        sys.exit(1)
    return board


def load_claims() -> set[str]:
    """Return claimed ticket ids; warn when falling back to local branches."""
    try:
        branches, source = agent_branches()
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    if source == "local":
        print(
            "note: no 'origin' remote; using local agent/* branches as claims.",
            file=sys.stderr,
        )
    return claimed_ids(branches)


def print_errors(errors: list[str]) -> None:
    for error in errors:
        print(f"E {error}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_check(_: argparse.Namespace) -> int:
    directory = tickets_dir()
    board = load_board(directory)
    if board.errors:
        print_errors(board.errors)
        print(
            f"tickets: {len(board.errors)} error(s) in {display(directory)}",
            file=sys.stderr,
        )
        return 1
    print(f"tickets: {len(board.tickets)} ticket(s) OK in {display(directory)}")
    return 0


def cmd_next(options: argparse.Namespace) -> int:
    board = require_board()
    claimed = load_claims()
    rows = [
        ticket
        for ticket in (board.tickets[key] for key in sorted(board.tickets))
        if (options.tier is None or ticket.tier == options.tier)
        and not blockers(ticket, board, claimed)
    ]
    if not rows:
        print("No claimable tickets.")
        return 0
    for ticket in rows:
        print(f"{ticket.id}\t{ticket.title}\t{ticket.branch}")
    return 0


def claim_commands(branch: str) -> list[list[str]]:
    """Return the git commands that claim *branch* atomically."""
    return [
        ["git", "fetch", "origin", "main"],
        [
            "git",
            "push",
            f"--force-with-lease=refs/heads/{branch}:",
            "origin",
            f"origin/main:refs/heads/{branch}",
        ],
        ["git", "fetch", "origin", branch],
        ["git", "branch", "--track", branch, f"origin/{branch}"],
    ]


def cmd_claim(options: argparse.Namespace) -> int:
    ticket_id = options.ticket_id
    if not TICKET_ID_RE.match(ticket_id):
        print(f"error: '{ticket_id}' is not a ticket id (T-NNN)", file=sys.stderr)
        return 2
    if options.dry_run:
        return dry_run_claim(ticket_id)
    board = require_board()
    ticket = board.tickets.get(ticket_id)
    if ticket is None:
        print(
            f"error: {ticket_id} not found in {display(tickets_dir())}", file=sys.stderr
        )
        return 1
    if not has_origin():
        print("error: claim needs an 'origin' remote.", file=sys.stderr)
        return 2
    reasons = blockers(ticket, board, load_claims())
    if reasons:
        print(f"{ticket_id} is not claimable:", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 1
    return run_claim(ticket)


def dry_run_claim(ticket_id: str) -> int:
    """Print the claim commands without running them."""
    board = load_board(tickets_dir())
    ticket = board.tickets.get(ticket_id)
    if ticket and ticket.branch:
        branch = ticket.branch
    else:
        branch = f"agent/{ticket_id}-<slug>"
        print(f"note: {ticket_id} not found; showing the branch as {branch}.")
    print("Dry run. The claim runs these commands:")
    for command in claim_commands(branch):
        print("  " + " ".join(command))
    return 0


def run_claim(ticket: Ticket) -> int:
    """Run the claim; the push fails if the branch already exists."""
    fetch, push, fetch_branch, track = claim_commands(ticket.branch)
    try:
        git(*fetch[1:])
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = git(*push[1:], check=False)
    if result.returncode != 0:
        print(
            f"{ticket.id} is taken: {ticket.branch} already exists on origin "
            "or the push was rejected.",
            file=sys.stderr,
        )
        print(result.stderr.strip(), file=sys.stderr)
        return 1
    try:
        git(*fetch_branch[1:])
        git(*track[1:])
    except GitError as exc:
        print(f"Claimed on origin, but local setup failed: {exc}", file=sys.stderr)
        return 2
    print(f"Claimed {ticket.id}: {ticket.branch} (tracking origin/{ticket.branch})")
    return 0


def cmd_show(options: argparse.Namespace) -> int:
    board = load_board(tickets_dir())
    ticket = board.tickets.get(options.ticket_id)
    if ticket is None:
        print_errors(board.errors)
        print(f"error: {options.ticket_id} not found or invalid", file=sys.stderr)
        return 1
    print(ticket.path.read_text(encoding="utf-8").rstrip())
    print("\n---")
    if board.errors:
        print("Claimability: unknown, the board has validation errors:")
        for error in board.errors:
            print(f"  - {error}")
        return 1
    reasons = blockers(ticket, board, load_claims())
    if reasons:
        print("Claimability: not claimable")
        for reason in reasons:
            print(f"  - {reason}")
    else:
        print(f"Claimability: claimable (run 'tickets.py claim {ticket.id}')")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate, list, claim, and show docs/tickets/ tickets."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Validate every ticket (gate).").set_defaults(
        func=cmd_check
    )
    nxt = sub.add_parser("next", help="List claimable tickets.")
    nxt.add_argument("--tier", choices=TIERS, help="Only list this tier.")
    nxt.set_defaults(func=cmd_next)
    claim = sub.add_parser("claim", help="Claim a ticket by pushing its branch.")
    claim.add_argument("ticket_id", metavar="ID")
    claim.add_argument(
        "--dry-run", action="store_true", help="Print the commands only."
    )
    claim.set_defaults(func=cmd_claim)
    show = sub.add_parser("show", help="Print a ticket and its claimability.")
    show.add_argument("ticket_id", metavar="ID")
    show.set_defaults(func=cmd_show)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    return options.func(options)


if __name__ == "__main__":
    sys.exit(main())
