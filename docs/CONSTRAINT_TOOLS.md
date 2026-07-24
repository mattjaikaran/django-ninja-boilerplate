# Constraint Tools

> "I need to have the agents write the tools that check the constraints. Those tools
> are deterministic. They are relatively small programs that check the quality of the
> code or check the coverage of the tests or manipulate the code and look for errors."
>
> — [Uncle Bob Martin, SwarmForge](https://github.com/unclebob/swarm-forge)

## Philosophy

When AI agents write code, **you need a way to trust that code without reading every line.**
The answer isn't more human review — it's better automated constraints.

Constraint tools are deterministic programs that produce a binary pass/fail result.
They don't require human judgment. They don't have opinions. They catch real defects.
If code survives all constraint tools, you can trust it. The tools become the reader.

This is the fundamental insight from Uncle Bob's SwarmForge project: surround agents
with extreme constraints, and the agents themselves can write and maintain those
constraint-checking tools. It's a virtuous cycle:

1. Agent writes feature code
2. Constraint tools reject bad code
3. Agent fixes the code (or the constraint tool)
4. Human only intervenes on constraint *design*, never on individual code review

## Properties of Good Constraint Tools

| Property | Why it matters |
|----------|---------------|
| **Deterministic** | Same input → same output. No flaky results. No "works on my machine." |
| **Small** | Under 400 lines. Easy to audit, easy to reason about, easy for agents to maintain. |
| **Fast** | Quick feedback loop. Developers (and agents) shouldn't wait minutes for a check. |
| **Binary** | Pass or fail. No "warnings" that get ignored. No severity levels to debate. |
| **Composable** | Each tool checks one concern. Chain them in a pipeline (the gauntlet). |
| **Self-enforcing** | The constraint tools are themselves subject to the constraints (file length, types, lint). |
| **Agent-writable** | AI agents can create, extend, debug, and fix these tools. Well-defined spec, clear inputs. |

## Our Constraint Tools

| Tool | Lines | What it checks |
|------|-------|----------------|
| `scripts/check_architecture.py` | ~270 | Layer violations, cross-app coupling, reverse dependencies |
| `scripts/check_file_length.py` | ~150 | Files exceeding 400-line limit (configurable per-file) |
| `scripts/gauntlet.py` | ~400 | Orchestrates all gates, reports results, generates CI artifacts |

Plus third-party deterministic tools integrated as gates:

| Tool | Gate | What it checks |
|------|------|----------------|
| `ruff format --check` | FORMAT | Code formatting consistency |
| `ruff check` | LINT | 50+ rule categories: bugs, anti-patterns, dead code |
| `mypy` | TYPECHECK | Type safety, missing annotations |
| `bandit` | SECURITY | SQL injection, XSS, hardcoded secrets, crypto issues |
| `pytest --cov-fail-under` | TEST | Broken functionality, coverage regression |
| `mutmut` | MUTATION | Tests that don't actually catch bugs |
| `pip-audit` | AUDIT | Known vulnerabilities in dependencies |
| `manage.py check --deploy` | DEPLOY | Production Django configuration |

## Writing a New Constraint Tool

### Template

```python
#!/usr/bin/env python3
"""One-line description of what this tool checks.

Usage:
    python scripts/check_something.py [files...]
    python scripts/check_something.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def check_file(filepath: Path) -> list[str]:
    """Check a single file. Return list of violation messages."""
    violations = []
    # ... deterministic checks ...
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check something")
    parser.add_argument("files", nargs="*", help="Files to check")
    parser.add_argument("--all", action="store_true", help="Check all files")
    args = parser.parse_args()

    # Collect files
    files = collect_files(args.files, args.all)

    # Check each file
    all_violations = []
    for f in files:
        all_violations.extend(check_file(f))

    # Report
    if all_violations:
        for v in all_violations:
            print(f"  {v}")
        return 1

    print(f"Check passed ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Registering in the Gauntlet

Add a method to `GauntletRunner` in `scripts/gauntlet.py`:

```python
def _gate_something(self) -> GateResult:
    return self.run_gate(
        "SOMETHING",
        ["uv", "run", "python", "scripts/check_something.py", "--all"],
    )
```

Then register it in `_build_gate_list()`:

```python
gates["something"] = self._gate_something
```

### Checklist

- [ ] Deterministic (no randomness, no network calls, no time-dependent behavior)
- [ ] Under 400 lines
- [ ] Exits 0 on pass, 1 on fail
- [ ] Prints clear violation messages with file:line references
- [ ] Has `--all` flag for full-project scan
- [ ] Accepts file list for pre-commit hook integration
- [ ] Type-hinted, passes mypy
- [ ] Passes ruff lint and format

## The Virtuous Cycle

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   Agent writes code                                 │
│        │                                            │
│        ▼                                            │
│   Gauntlet runs constraint tools                    │
│        │                                            │
│        ├── PASS → Code is trustworthy               │
│        │                                            │
│        └── FAIL → Agent reads error, fixes code     │
│              │                                      │
│              ▼                                      │
│         Gauntlet runs again                         │
│              │                                      │
│              └── Loop until PASS                    │
│                                                     │
│   Human intervention only for:                      │
│     • Designing new constraints                     │
│     • Changing architecture rules                   │
│     • Adjusting thresholds (coverage ratchet)       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Further Reading

- [SwarmForge](https://github.com/unclebob/swarm-forge) — Uncle Bob Martin's tmux-based
  agent orchestration platform with constitution-driven constraints
- [The Gauntlet](../CLAUDE.md#the-gauntlet) — see `CLAUDE.md` for the full gate table and agent rules
- [Architecture Rules](ARCHITECTURE.md) — the layer enforcement philosophy in detail
