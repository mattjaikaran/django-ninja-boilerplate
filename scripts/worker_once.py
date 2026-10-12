#!/usr/bin/env python3
"""Run one iteration of the worker loop: claim, work, verify, open a PR.

Steps:
  1. Pick the first claimable `tier: small` ticket, or the one in --ticket.
  2. Claim it with the atomic push from scripts/tickets.py.
  3. Create a worktree at ${WORKER_WORKTREES:-~/worktrees/<repo>}/T-NNN.
  4. Run $WORKER_AGENT_CMD in the worktree with a short prompt. The output
     goes to /tmp/T-NNN-agent.log. Timeout: $WORKER_TIMEOUT seconds (3600).
  5. Run the ticket's `## Verify` commands and `just gauntlet-quick`. The
     output goes to /tmp/verify.log with `exit=` markers.
  6. On success: check the diff stays within `owns`, commit leftovers, push,
     and open a PR (`--reviewer $WORKER_REVIEWER` when set).
  7. On failure: write a redacted /tmp/T-NNN-failure.md, push, and open a
     draft PR labeled `needs-planner`.

Usage:
    uv run python scripts/worker_once.py [--ticket T-NNN] [--dry-run]

Exit: 0 = PR opened or dry run, 1 = stopped with a draft PR,
      2 = nothing to do or setup error
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import redact_log
import tickets

ROOT = tickets.PROJECT_ROOT
SKILL = ".agents/skills/ticket-worker/SKILL.md"
VERIFY_LOG = Path("/tmp/verify.log")
DEFAULT_TIMEOUT = 3600
PROMPT = (
    "You are a worker model. Read the skill at {skill} and follow it. "
    "Execute the ticket at {ticket}. The ticket is already claimed and this "
    "directory is its worktree on branch {branch}. Edit only the files in "
    "owns, plus `status: done` in the ticket. Commit your work with a "
    "Conventional Commits message. Do not push, do not open a PR, do not "
    "claim another ticket. If you must stop, write one line starting with "
    "'Blocked:' to {blocked} and exit."
)
RETRY_PROMPT = (
    "Verify failed for the ticket at {ticket}: {failure}. Fix only what fails, "
    "within owns. Follow the same rules as before: commit, do not push. If "
    "you cannot fix it, write one line starting with 'Blocked:' to {blocked} "
    "and exit. Redacted last 50 lines of /tmp/verify.log:\n{log}"
)
HERDR_HELP = (
    "Herdr: run one loop per pane. Exit 1 (stopped) moves on, exit 2 ends it:\n"
    "  while uv run python scripts/worker_once.py || [ $? -eq 1 ]; do :; done\n"
    "Start it in a pane with `herdr pane run <PANE_ID> <COMMAND>...`\n"
)


class Stop(Exception):
    """A ticket failure that ends in a draft PR."""


class Runner:
    """Run commands, or print them in dry-run mode."""

    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run

    def show(self, command: list[str], cwd: Path | None, note: str = "") -> None:
        where = f"  (in {cwd})" if cwd and cwd != ROOT else ""
        suffix = f"  # {note}" if note else ""
        print(f"  $ {shlex.join(command)}{where}{suffix}")

    def run(
        self, command: list[str], cwd: Path = ROOT, note: str = ""
    ) -> subprocess.CompletedProcess[str]:
        """Run *command*; in dry-run mode print it and return success."""
        self.show(command, cwd, note)
        if self.dry_run:
            return subprocess.CompletedProcess(command, 0, "", "")
        # Argument list, no shell.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        return subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=False
        )

    def must(self, command: list[str], cwd: Path = ROOT, note: str = "") -> str:
        result = self.run(command, cwd, note)
        if result.returncode != 0:
            raise RuntimeError(f"{shlex.join(command)} failed: {result.stderr.strip()}")
        return result.stdout


def local_claims() -> set[str]:
    """Claimed ids from local agent/* branches (no network, for dry runs)."""
    out = tickets.git(
        "for-each-ref", "--format=%(refname:short)", "refs/heads/agent/", check=False
    ).stdout
    return tickets.claimed_ids({b.strip() for b in out.splitlines() if b.strip()})


def pick(board: tickets.Board, wanted: str | None, dry_run: bool) -> tickets.Ticket:
    """Return the ticket to work; raise SystemExit(2) when there is none."""
    claimed = local_claims() if dry_run else tickets.load_claims()
    if wanted:
        ticket = board.tickets.get(wanted)
        if ticket is None:
            print(f"error: {wanted} not found", file=sys.stderr)
            raise SystemExit(2)
        reasons = tickets.blockers(ticket, board, claimed)
        if ticket.tier != "small":
            reasons.append(f"tier is '{ticket.tier}', not 'small'")
        if reasons:
            print(f"{wanted} is not claimable: {'; '.join(reasons)}", file=sys.stderr)
            raise SystemExit(2)
        return ticket
    for key in sorted(board.tickets):
        ticket = board.tickets[key]
        if ticket.tier == "small" and not tickets.blockers(ticket, board, claimed):
            return ticket
    print("result: nothing to do (no claimable small tickets)")
    raise SystemExit(2)


def worktree_root() -> Path:
    override = os.environ.get("WORKER_WORKTREES")
    if override:
        return Path(override).expanduser()
    return Path.home() / "worktrees" / ROOT.name


def ticket_rel(ticket: tickets.Ticket) -> str:
    """Return the ticket path relative to the repo when possible."""
    try:
        return str(ticket.path.resolve().relative_to(ROOT))
    except ValueError:
        return str(ticket.path)


def within_owns(path: str, ticket: tickets.Ticket, ticket_path: str) -> bool:
    if path == ticket_path:
        return True
    return any(tickets.paths_overlap(path, entry) for entry in ticket.owns)


def agent_command(runner: Runner) -> list[str]:
    agent_cmd = os.environ.get("WORKER_AGENT_CMD", "")
    if not agent_cmd and runner.dry_run:
        agent_cmd = "$WORKER_AGENT_CMD"
    elif not agent_cmd:
        raise RuntimeError("WORKER_AGENT_CMD is not set (for example 'claude -p')")
    return shlex.split(agent_cmd)


def blocked_file(ticket: tickets.Ticket) -> Path:
    return Path(f"/tmp/{ticket.id}-blocked.txt")


def run_agent(
    runner: Runner, ticket: tickets.Ticket, tree: Path, prompt: str, append: bool
) -> None:
    """Run $WORKER_AGENT_CMD with *prompt*; raise Stop on error or timeout."""
    command = [*agent_command(runner), prompt]
    timeout = int(os.environ.get("WORKER_TIMEOUT", DEFAULT_TIMEOUT))
    log = Path(f"/tmp/{ticket.id}-agent.log")
    arrow = ">>" if append else ">"
    runner.show([*command[:-1], "<prompt>"], tree, f"{arrow} {log}, timeout {timeout}s")
    if runner.dry_run:
        print(f"    prompt: {prompt}")
        return
    with log.open("a" if append else "w", encoding="utf-8") as out:
        try:
            # Argument list, no shell; the command comes from the operator.
            # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
            code = subprocess.run(
                command,
                cwd=tree,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            ).returncode
        except subprocess.TimeoutExpired as exc:
            raise Stop(f"agent timed out after {timeout}s") from exc
    blocked = blocked_file(ticket)
    if blocked.is_file():
        text = blocked.read_text(encoding="utf-8").strip()
        raise Stop(text.removeprefix("Blocked:").strip() or "agent wrote Blocked")
    if code != 0:
        raise Stop(f"agent exited {code} (see {log})")


def verify_steps(ticket: tickets.Ticket) -> list[list[str]]:
    """One shell per fenced Verify block, then the quick gauntlet."""
    text = ticket.sections.get("Verify", "")
    steps = [
        ["bash", "-o", "pipefail", "-c", block.strip()]
        for block in tickets.FENCE_RE.findall(text)
        if block.strip()
    ]
    steps.append(["just", "gauntlet-quick"])
    return steps


def run_verify(runner: Runner, ticket: tickets.Ticket, tree: Path) -> None:
    """Run Verify blocks and the quick gauntlet; raise Stop on a failure."""
    print(f"  Verify (appends to {VERIFY_LOG} with exit= markers):")
    for command in verify_steps(ticket):
        runner.show(command, tree)
        if runner.dry_run:
            continue
        with VERIFY_LOG.open("a", encoding="utf-8") as log:
            log.write(f"$ {shlex.join(command)}\n")
            log.flush()
            # Argument list; Verify blocks are planner-written shell commands.
            # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
            code = subprocess.run(
                command, cwd=tree, stdout=log, stderr=subprocess.STDOUT, check=False
            ).returncode
            log.write(f"exit={code}\n")
        if code != 0:
            raise Stop(f"`{shlex.join(command)}` exited {code}")


def redacted_tail() -> str:
    """Return the last 50 lines of verify.log, passed through redact_log."""
    if not VERIFY_LOG.is_file():
        return ""
    lines = VERIFY_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    return redact_log.redact("\n".join(lines[-50:]), redact_log.secret_values(ROOT))


def attempt(runner: Runner, ticket: tickets.Ticket, tree: Path) -> None:
    """Agent + Verify; one retry with the failure log. Raise Stop on 2nd failure."""
    rel = ticket_rel(ticket)
    prompt = PROMPT.format(
        skill=SKILL, ticket=rel, branch=ticket.branch, blocked=blocked_file(ticket)
    )
    run_agent(runner, ticket, tree, prompt, append=False)
    try:
        run_verify(runner, ticket, tree)
        if not runner.dry_run:
            return
        first = "<first failure>"
    except Stop as exc:
        first = str(exc)
    print(f"Retry (only after the first Verify failure: {first}):")
    log = (
        "<redacted last 50 lines of verify.log>" if runner.dry_run else redacted_tail()
    )
    retry = RETRY_PROMPT.format(
        ticket=rel, failure=first, log=log, blocked=blocked_file(ticket)
    )
    run_agent(runner, ticket, tree, retry, append=True)
    run_verify(runner, ticket, tree)


def check_owns(runner: Runner, ticket: tickets.Ticket, tree: Path) -> None:
    rel = ticket_rel(ticket)
    runner.must(["git", "add", "-A"], tree)
    base = runner.must(["git", "merge-base", "origin/main", "HEAD"], tree).strip()
    out = runner.must(
        ["git", "diff", "--cached", "--name-only", base or "<merge-base>"],
        tree,
        "branch changes since the merge base, including uncommitted work",
    )
    outside = [p for p in out.split() if not within_owns(p, ticket, rel)]
    if outside:
        raise Stop(f"changed files outside owns: {', '.join(outside)}")


def commit_leftovers(runner: Runner, tree: Path, message: str, empty: bool) -> None:
    """Commit staged changes; with *empty*, commit even when nothing changed."""
    runner.must(["git", "add", "-A"], tree)
    staged = runner.run(["git", "diff", "--cached", "--quiet"], tree).returncode != 0
    if staged or runner.dry_run:
        runner.must(["git", "commit", "-m", message], tree, "only if changes remain")
    if empty:
        ahead = runner.must(["git", "rev-list", "--count", "origin/main..HEAD"], tree)
        if not runner.dry_run and ahead.strip() == "0":
            runner.must(["git", "commit", "--allow-empty", "-m", message], tree)


def pr_command(ticket: tickets.Ticket, body: Path, draft: bool) -> list[str]:
    command = ["gh", "pr", "create"]
    if draft:
        command += ["--draft", "--label", "needs-planner"]
    command += [
        "--base",
        "main",
        "--head",
        ticket.branch,
        "--title",
        f"{ticket.id} {ticket.title}",
        "--body-file",
        str(body),
    ]
    reviewer = os.environ.get("WORKER_REVIEWER")
    if reviewer:
        command += ["--reviewer", reviewer]
    return command


def write(runner: Runner, path: Path, text: str) -> None:
    if runner.dry_run:
        print(f"  write {path}:")
        print("    " + text.strip().replace("\n", "\n    "))
        return
    path.write_text(text, encoding="utf-8")


def succeed(runner: Runner, ticket: tickets.Ticket, tree: Path) -> int:
    check_owns(runner, ticket, tree)
    commit_leftovers(runner, tree, f"chore(tickets): Complete {ticket.id}", empty=False)
    runner.must(["git", "push", "origin", ticket.branch], tree)
    body = Path(f"/tmp/{ticket.id}-pr.md")
    write(
        runner,
        body,
        f"Ticket: {ticket_rel(ticket)}\n\nVerify and `just gauntlet-quick` passed.\n",
    )
    url = runner.must(pr_command(ticket, body, draft=False), tree).strip()
    if not runner.dry_run:
        print(f"result: {ticket.id} PR opened {url}".rstrip())
    return 0


def stop(runner: Runner, ticket: tickets.Ticket, tree: Path, reason: str) -> int:
    log = "<redacted last 50 lines>" if runner.dry_run else redacted_tail()
    body = Path(f"/tmp/{ticket.id}-failure.md")
    write(
        runner,
        body,
        f"Blocked: {reason}\n\nTicket: {ticket_rel(ticket)}\n\n"
        f"Last 50 lines of verify.log (redacted):\n\n```\n{log}\n```\n",
    )
    rel = ticket_rel(ticket)
    if not Path(rel).is_absolute():
        runner.must(
            ["git", "checkout", "origin/main", "--", rel],
            tree,
            "keep the ticket status unchanged on a stop",
        )
    commit_leftovers(runner, tree, f"chore(tickets): Block {ticket.id}", empty=True)
    runner.must(["git", "push", "origin", ticket.branch], tree)
    url = runner.must(pr_command(ticket, body, draft=True), tree).strip()
    if not runner.dry_run:
        print(f"result: {ticket.id} stopped ({reason}); draft PR {url}".rstrip())
    return 1


def reset_logs(runner: Runner, ticket: tickets.Ticket) -> None:
    """Start this iteration with an empty verify.log and no stale Blocked file."""
    print(f"  reset {VERIFY_LOG}; remove {blocked_file(ticket)}")
    if runner.dry_run:
        return
    VERIFY_LOG.write_text(f"=== {ticket.id}\n", encoding="utf-8")
    blocked_file(ticket).unlink(missing_ok=True)


def work(runner: Runner, ticket: tickets.Ticket) -> int:
    tree = worktree_root() / ticket.id
    print(f"Claim {ticket.id} ({ticket.branch}):")
    if runner.dry_run:
        for command in tickets.claim_commands(ticket.branch):
            runner.show(command, ROOT)
    elif tickets.run_claim(ticket) != 0:
        return 2
    print("Worktree:")
    runner.must(["git", "worktree", "add", str(tree), ticket.branch])
    reset_logs(runner, ticket)
    print("Agent:")
    try:
        try:
            attempt(runner, ticket, tree)
            print("On success:")
            return succeed(runner, ticket, tree)
        finally:
            if runner.dry_run:
                print("On failure (agent error, 2nd Verify fail, owns violation):")
                stop(runner, ticket, tree, "<reason>")
    except Stop as exc:
        return stop(runner, ticket, tree, str(exc))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one worker-loop iteration on a small ticket.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment: WORKER_AGENT_CMD (required, for example 'claude -p', "
            "'omp -p', 'opencode run'),\nWORKER_TIMEOUT (default 3600), "
            "WORKER_WORKTREES, WORKER_REVIEWER, TICKETS_DIR.\n"
            "Exit: 0 PR opened or dry run, 1 stopped with draft PR, "
            "2 nothing to do or setup error.\n\n" + HERDR_HELP
        ),
    )
    parser.add_argument("--ticket", metavar="T-NNN", help="work this ticket")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print every command; no network, agent, or git writes",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    if options.ticket and not tickets.TICKET_ID_RE.match(options.ticket):
        print(f"error: '{options.ticket}' is not a ticket id (T-NNN)", file=sys.stderr)
        return 2
    runner = Runner(options.dry_run)
    try:
        if not options.dry_run:
            missing = [t for t in ("git", "gh", "just") if shutil.which(t) is None]
            if not os.environ.get("WORKER_AGENT_CMD"):
                missing.append("WORKER_AGENT_CMD")
            if missing:
                print(f"result: setup error: missing {', '.join(missing)}")
                return 2
        print("Update main checkout:")
        runner.must(["git", "fetch", "origin", "main"])
        runner.must(["git", "merge", "--ff-only", "origin/main"])
        board = tickets.require_board()
        ticket = pick(board, options.ticket, options.dry_run)
    except RuntimeError as exc:
        print(f"result: setup error: {exc}")
        return 2
    except SystemExit as exc:
        return int(exc.code or 0) if exc.code != 1 else 2
    if options.dry_run:
        print(f"Dry run for {ticket.id}: {ticket.title}")
    try:
        code = work(runner, ticket)
    except RuntimeError as exc:
        print(f"result: setup error: {exc}", file=sys.stderr)
        return 2
    if options.dry_run:
        print(f"result: dry run for {ticket.id}; nothing changed")
        return 0
    return code


if __name__ == "__main__":
    raise SystemExit(main())
