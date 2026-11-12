#!/usr/bin/env python
"""Print a fast, read-only project summary for an agent starting a session.

Sections: worktree, git, stack, tickets, journeys, gauntlet, OpenAPI. Reads
local refs, files, and Docker state only. Makes no network calls and does not
set up Django.

Usage:
    python scripts/agent_status.py --json   # same data as JSON
    python scripts/agent_status.py --brief  # short start for agent-start
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

GAUNTLET_REPORT = ROOT / ".gauntlet" / "last" / "report.json"
OPENAPI_FILE = ROOT / "docs" / "openapi" / "openapi.json"
SOURCE_PATHSPECS = (":(glob)*/controllers/**", ":(glob)*/schemas/**", "api/urls.py")
NEXT_LIMIT = 3


def git(*args: str) -> str | None:
    """Run a local git command; return stripped stdout or None on failure."""
    try:
        proc = subprocess.run(
            ["git", "--no-optional-locks", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_status() -> dict[str, Any]:
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    ahead = behind = None
    counts = git("rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if counts is None:
        counts = git("rev-list", "--left-right", "--count", f"HEAD...origin/{branch}")
    if counts:
        left, right = counts.split()
        ahead, behind = int(left), int(right)
    porcelain = git("status", "--porcelain") or ""
    return {
        "branch": branch,
        "ahead": ahead,
        "behind": behind,
        "dirty_files": len([line for line in porcelain.splitlines() if line]),
        "last_commit": git("log", "-1", "--format=%s") or "",
    }


def local_claims() -> set[str]:
    """Ticket ids claimed by local or origin agent/T-* branches (local refs)."""
    import tickets

    refs = git(
        "for-each-ref",
        "--format=%(refname)",
        "refs/heads/agent/",
        "refs/remotes/origin/agent/",
    )
    names = set()
    for ref in (refs or "").splitlines():
        for prefix in ("refs/heads/", "refs/remotes/origin/"):
            if ref.startswith(prefix):
                names.add(ref[len(prefix) :])
    return tickets.claimed_ids(names)


def ticket_status() -> dict[str, Any]:
    try:
        import tickets

        board = tickets.load_board(tickets.tickets_dir())
    except Exception as exc:
        return {"error": str(exc)}
    claimed = local_claims()
    counts = Counter(t.status for t in board.tickets.values())
    claimable = [
        {"id": t.id, "title": t.title}
        for t in (board.tickets[k] for k in sorted(board.tickets))
        if t.tier == "small" and not tickets.blockers(t, board, claimed)
    ]
    return {
        "counts": dict(sorted(counts.items())),
        "claimed": sorted(claimed),
        "next_small": claimable[:NEXT_LIMIT],
        "board_errors": len(board.errors),
    }


def journey_status() -> dict[str, Any]:
    try:
        from journeys.services.spec_service import build_report, spec_paths

        report = build_report(spec_paths(ROOT))
    except Exception as exc:
        return {"error": str(exc)}
    return {
        "verified": report.verified_journeys,
        "total": len(report.journeys),
        "errors": len(report.errors),
        "warnings": len(report.warnings),
        "gaps": len(report.gaps),
        "e2e_dir": report.e2e_dir_exists,
        "e2e_report": report.report_exists,
    }


def gauntlet_status() -> dict[str, Any]:
    if not GAUNTLET_REPORT.exists():
        return {"report": None}
    try:
        data = json.loads(GAUNTLET_REPORT.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return {"report": str(GAUNTLET_REPORT.name), "error": str(exc)}
    failed = [
        g["name"]
        for g in data.get("gates", [])
        if not g.get("passed") and not g.get("skipped") and not g.get("warning")
    ]
    return {
        "report": GAUNTLET_REPORT.name,
        "age_s": int(time.time() - GAUNTLET_REPORT.stat().st_mtime),
        "mode": data.get("mode"),
        "all_passed": data.get("all_passed"),
        "failed": failed,
    }


def openapi_status() -> dict[str, Any]:
    if not OPENAPI_FILE.exists():
        return {"exists": False, "stale": True, "reason": "missing"}
    spec = str(OPENAPI_FILE.relative_to(ROOT))
    dirty_src = git("status", "--porcelain", "--", *SOURCE_PATHSPECS) or ""
    dirty_spec = git("status", "--porcelain", "--", spec) or ""
    if dirty_src and not dirty_spec:
        first = dirty_src.splitlines()[0][3:]
        return {"exists": True, "stale": True, "reason": f"uncommitted {first}"}
    # Committed code is covered by the OPENAPI gate in the pre-push hook. A
    # commit-time comparison flags every route reorder, so only uncommitted
    # changes count here.
    return {"exists": True, "stale": False, "reason": None}


def worktree_status() -> dict[str, Any]:
    """Return the checkout path and whether it is a linked worktree."""
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    gitdir = git("rev-parse", "--path-format=absolute", "--git-dir")
    linked = bool(common and gitdir and Path(common) != Path(gitdir))
    return {"path": str(ROOT), "linked": linked}


def running_services(project: str) -> list[str]:
    """Return Compose service names of running containers in ``project``.

    Returns an empty list when Docker is missing or not running.
    """
    command = [
        "docker",
        "ps",
        "--filter",
        f"label=com.docker.compose.project={project}",
        "--format",
        '{{.Label "com.docker.compose.service"}}',
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    return sorted(set(completed.stdout.split()))


def stack_status() -> dict[str, Any]:
    """Return the Compose project, running services and dev port choices."""
    import dev_ports

    try:
        compose_text = (ROOT / dev_ports.COMPOSE_FILE).read_text()
        dotenv = dev_ports.load_env(ROOT / dev_ports.ENV_FILE)
        project = dev_ports.project_name(ROOT, compose_text, dotenv)
        resolution = dev_ports.resolve_ports(ROOT, {"dev"})
    except (OSError, ValueError, RuntimeError) as exc:
        return {"error": str(exc)}
    return {
        "project": project,
        "running": running_services(project),
        "ports": [
            {
                "name": r.var.name,
                "configured": r.port,
                "port": r.free_port,
                "moved": r.busy,
            }
            for r in resolution.results
        ],
    }


def collect() -> dict[str, Any]:
    return {
        "git": git_status(),
        "tickets": ticket_status(),
        "journeys": journey_status(),
        "gauntlet": gauntlet_status(),
        "openapi": openapi_status(),
    }


def human_age(seconds: int) -> str:
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds // size}{unit}"
    return f"{seconds}s"


def render(data: dict[str, Any], brief: bool = False) -> list[str]:
    w = data["worktree"]
    g = data["git"]
    sync = (
        f"+{g['ahead']}/-{g['behind']} vs upstream"
        if g["ahead"] is not None
        else "no upstream"
    )
    kind = "linked" if w["linked"] else "main checkout"
    lines = [
        f"Worktree: {w['path']} ({kind})",
        f"Git: {g['branch']} ({sync}), {g['dirty_files']} dirty",
        f"  last: {g['last_commit']}",
    ]
    s = data["stack"]
    if "error" in s:
        lines.append(f"Stack: error: {s['error']}")
    else:
        running = ", ".join(s["running"]) or "none"
        lines.append(f"Stack: project {s['project']}, running: {running}")
        moved = [
            f"{p['name']} {p['port']} (configured {p['configured']})"
            for p in s["ports"]
            if p["moved"]
        ]
        if moved:
            lines.append(f"  ports moved: {'; '.join(moved)}")
    t = data["tickets"]
    if "error" in t:
        lines.append(f"Tickets: error: {t['error']}")
    else:
        counts = ", ".join(f"{k} {v}" for k, v in t["counts"].items()) or "none"
        claimed = ", ".join(t["claimed"]) or "none"
        lines.append(f"Tickets: {counts}; claimed: {claimed}")
        if t["board_errors"]:
            lines.append(f"  {t['board_errors']} board errors: run just tickets-check")
        if t["next_small"]:
            lines.extend(f"  next: {n['id']} {n['title']}" for n in t["next_small"])
        else:
            lines.append("  next: no claimable small tickets")
    r = data["gauntlet"]
    if r["report"] is None:
        lines.append("Gauntlet: no report (run just gauntlet-quick)")
    elif "error" in r:
        lines.append(f"Gauntlet: unreadable report: {r['error']}")
    else:
        failed = ", ".join(r["failed"]) or "none"
        lines.append(
            f"Gauntlet: {r['mode']}, {human_age(r['age_s'])} ago, failed: {failed}"
        )
    if brief:
        return lines
    j = data["journeys"]
    if "error" in j:
        lines.append(f"Journeys: error: {j['error']}")
    else:
        lines.append(
            f"Journeys: verified {j['verified']}/{j['total']}, {j['errors']} errors, "
            f"{j['warnings']} warnings, {j['gaps']} gaps"
        )
        lines.append(
            f"  e2e dir {'found' if j['e2e_dir'] else 'missing'}, "
            f"report {'found' if j['e2e_report'] else 'missing'}"
        )
    o = data["openapi"]
    if not o["exists"]:
        lines.append("OpenAPI: missing, run just openapi-check")
    elif o["stale"]:
        lines.append(f"OpenAPI: maybe stale ({o['reason']}), run just openapi-check")
    else:
        lines.append("OpenAPI: no uncommitted route or schema changes")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print as JSON")
    parser.add_argument(
        "--brief", action="store_true", help="print the short session start"
    )
    args = parser.parse_args(argv)
    # The MCP tool serves collect() unchanged, so the CLI adds its keys here.
    data = {"worktree": worktree_status(), "stack": stack_status(), **collect()}
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print("\n".join(render(data, brief=args.brief)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
