"""Offline end-to-end runs of scripts/worker_once.py (real git, stub gh/agent).

Contract: a clean ticket ends in a pushed agent/* branch and a PR; a change
outside `owns` ends in exit 1 and a draft `needs-planner` PR.
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COPIED = (
    "scripts/tickets.py",
    "scripts/redact_log.py",
    "scripts/worker_once.py",
    ".agents/skills/ticket-worker/SKILL.md",
)
BRANCH = "agent/T-001-write-notes"
TICKET_PATH = "docs/tickets/T-001-write-notes.md"
TICKET = f"""---
id: T-001
title: Write notes
status: ready
tier: small
depends_on: []
owns:
  - notes.txt
shared: []
journeys: []
features: []
branch: {BRANCH}
---
## Context

Test ticket.

## Change

1. Create `notes.txt`.

## Do not

- Do not edit files outside `owns`.

## Verify

```bash
test -f notes.txt
```

## Done when

- [ ] `notes.txt` exists.
"""
AGENT = """
import os
import subprocess
from pathlib import Path

ticket = Path("docs/tickets/T-001-write-notes.md")
Path("notes.txt").write_text("notes\\n")
ticket.write_text(ticket.read_text().replace("status: ready", "status: done"))
if os.environ.get("STUB_OUTSIDE_OWNS"):
    Path("extra.txt").write_text("outside owns\\n")
subprocess.run(["git", "add", "-A"], check=True)
subprocess.run(["git", "commit", "-q", "-m", "docs: write notes"], check=True)
"""
GH = """
import json
import os
import sys

with open(os.environ["GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
print("https://example.test/pull/1")
"""


@pytest.fixture
def world(tmp_path):
    """A bare origin, a clone with one ready ticket, and stub gh and agent."""
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text(
        "[user]\n\tname = Test\n\temail = test@example.test\n"
        "[commit]\n\tgpgsign = false\n[init]\n\tdefaultBranch = main\n"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f"#!{sys.executable}\n{GH}")
    gh.chmod(0o755)
    agent = tmp_path / "agent.py"
    agent.write_text(AGENT)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("WORKER_", "GIT_", "TICKETS_DIR"))
    }
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env['PATH']}",
        GIT_CONFIG_GLOBAL=str(gitconfig),
        GIT_CONFIG_NOSYSTEM="1",
        GH_LOG=str(tmp_path / "gh.log"),
        WORKER_AGENT_CMD=shlex.join([sys.executable, str(agent)]),
        WORKER_GAUNTLET_CMD="true",
        WORKER_WORKTREES=str(tmp_path / "worktrees"),
        WORKER_LOG_DIR=str(tmp_path / "logs"),
        WORKER_TIMEOUT="60",
    )

    def git(cwd: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
        ).stdout

    origin = tmp_path / "origin.git"
    clone = tmp_path / "clone"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    for rel in COPIED:
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, clone / rel)
    (clone / TICKET_PATH).parent.mkdir(parents=True)
    (clone / TICKET_PATH).write_text(TICKET)
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "chore: seed")
    git(clone, "push", "-q", "origin", "main")

    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/worker_once.py"],
            cwd=clone,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def gh_calls() -> list[list[str]]:
        lines = (tmp_path / "gh.log").read_text().splitlines()
        return [json.loads(line) for line in lines]

    return {
        "env": env,
        "git": git,
        "origin": origin,
        "logs": tmp_path / "logs",
        "run": run,
        "gh_calls": gh_calls,
    }


def test_clean_ticket_pushes_branch_and_opens_pr(world):
    result = world["run"]()
    assert result.returncode == 0, result.stdout + result.stderr

    git, origin = world["git"], world["origin"]
    heads = git(origin, "for-each-ref", "--format=%(refname:short)", "refs/heads/")
    assert BRANCH in heads.split()
    changed = git(origin, "diff", "--name-only", "main", BRANCH).split()
    assert sorted(changed) == [TICKET_PATH, "notes.txt"]
    assert "status: done" in git(origin, "show", f"{BRANCH}:{TICKET_PATH}")

    [call] = world["gh_calls"]()
    assert call[:2] == ["pr", "create"]
    assert call[call.index("--head") + 1] == BRANCH
    assert "--draft" not in call


def test_change_outside_owns_stops_with_draft_pr(world):
    world["env"]["STUB_OUTSIDE_OWNS"] = "1"
    result = world["run"]()
    assert result.returncode == 1, result.stdout + result.stderr

    [call] = world["gh_calls"]()
    assert call[:5] == ["pr", "create", "--draft", "--label", "needs-planner"]
    assert call[call.index("--head") + 1] == BRANCH
    body = Path(call[call.index("--body-file") + 1])
    assert body == world["logs"] / "T-001" / "failure.md"
    assert body.read_text().startswith(
        "Blocked: changed files outside owns: extra.txt\n"
    )
    # A stop restores the ticket, so the planner sees it still ready.
    git, origin = world["git"], world["origin"]
    assert "status: ready" in git(origin, "show", f"{BRANCH}:{TICKET_PATH}")
