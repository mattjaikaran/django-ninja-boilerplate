# The Portable Gauntlet Pattern

How to take the four-layer convention enforcement system and apply it to any codebase, any language, any framework.

## The Problem

AI coding agents produce "slop" — code that compiles but violates conventions:
- Using the wrong framework (DRF instead of Django Ninja)
- Wrong import patterns (raw Schema instead of CamelCaseSchema)
- Business logic in the wrong layer (controllers instead of services)
- Missing decorators, wrong decorator order
- Redeclaring inherited fields
- Unscoped queries

Linters and type checkers don't catch these. They're convention violations, not syntax or type errors.

## The Solution: Four-Layer Defense

```
LAYER 1: System Prompt    →  "Here's what NOT to do"
LAYER 2: Always-Apply Rules → "Here are the conventions"
LAYER 3: TTSR Rules        →  "STOP — you just violated a rule"
LAYER 4: Gauntlet Gates    →  Deterministic pass/fail verification
```

### Layer 1: System Prompt Injection (`.omp/APPEND_SYSTEM.md`)

A short document injected into every AI session. Contains:
- Framework identity ("This is X, NOT Y")
- The top 5-10 things the model WILL get wrong
- Prohibited patterns with correct alternatives
- Reference to rule files for details

**Key principle**: Keep it SHORT. The model reads this every turn. Focus on what it drifts toward, not a full style guide.

### Layer 2: Always-Apply Rules (`.omp/rules/*.md` with `alwaysApply: true`)

Full convention reference injected into the system prompt. Contains:
- Complete naming conventions
- File structure templates
- Decorator order rules
- Layer architecture contracts
- Wrong vs. right code examples

**Key principle**: These are always in context. Make them reference-able via `rule://<name>`.

### Layer 3: TTSR Mid-Generation Rules (`.omp/rules/ttsr-*.md` with `condition`/`astCondition`)

Rules that fire DURING code generation when the model's output stream matches a pattern:
- `condition`: regex patterns that trigger when matched in the output stream
- `astCondition`: AST patterns that trigger when matched in edit/write operations
- `interruptMode: always` forces the model to stop and read the rule

**Key principle**: Catch the model BEFORE it commits the violation. TTSR is your last line of defense before the code hits disk.

### Layer 4: Deterministic Gauntlet Gates (`scripts/check_*.py`)

Small Python scripts (under 600 lines) that check conventions deterministically:
- Each check is a function that yields `Violation` objects
- Exit 0 = pass, exit 1 = violations found
- Composible: the gauntlet orchestrator chains them

**Key principle**: If it passes, you don't need to read the code. The tool IS the review.

## Adapting to Your Codebase

### Step 1: Document Your Conventions

Write down what the AI consistently gets wrong. Be specific:

```markdown
# WRONG — AI does this:
from old_framework import Thing

# CORRECT — should do this:
from new_framework import Thing
```

### Step 2: Create Always-Apply Rules

For each convention domain, create a rule file:

```
.omp/rules/
├── framework-identity.md    # "This is X, not Y"
├── naming-conventions.md    # How to name things
├── layer-architecture.md    # What goes where
└── anti-patterns.md         # Wrong vs. right
```

### Step 3: Add TTSR Triggers

For patterns the model commonly drifts toward, add TTSR rules:

```yaml
---
description: Interrupts when model uses wrong framework
condition:
  - "from old_framework"
  - "import old_pattern"
interruptMode: always
scope:
  - "tool:edit(**/*.py)"
---
```

### Step 4: Write Convention Checkers

Template for a convention checker:

```python
@dataclass
class Violation:
    check: str
    filepath: str
    line: int
    message: str

class MyChecker:
    def check_no_old_pattern(self) -> Iterator[Violation]:
        for fpath in self.collect_files():
            for i, line in enumerate(fpath.read_text().splitlines(), 1):
                if "old_pattern" in line:
                    yield Violation("OLD_PATTERN", str(fpath), i, "Use new_pattern")
```

### Step 5: Register in the Gauntlet

```python
gates["conventions"] = self._gate_conventions

def _gate_conventions(self) -> GateResult:
    return self.run_gate("CONVENTIONS", ["python", "scripts/check_conventions.py"])
```

## Language-Agnostic Principles

The four-layer pattern works for ANY language:

| Layer | Python | TypeScript | Go | Rust |
|-------|--------|-----------|-----|------|
| System Prompt | APPEND_SYSTEM.md | APPEND_SYSTEM.md | APPEND_SYSTEM.md | APPEND_SYSTEM.md |
| Always-Apply Rules | .omp/rules/*.md | .omp/rules/*.md | .omp/rules/*.md | .omp/rules/*.md |
| TTSR Rules | regex + ast-grep | regex + ast-grep | regex | regex |
| Gauntlet Gates | Python scripts | Python/Node scripts | Python/Go scripts | Python/Rust scripts |

The convention checker can be in any language — the gauntlet orchestrator just runs executables.

## What Makes a Good Convention Check

1. **Deterministic** — same input always produces same output. No flaky heuristics.
2. **Small** — under 600 lines. One check = one function.
3. **Specific** — catches exactly one class of violation. Don't combine unrelated checks.
4. **Actionable** — the violation message tells you exactly what to fix and why.
5. **Zero false positives** — if the checker says it's wrong, it IS wrong. No "maybe" violations.

## Anti-Patterns in Convention Checkers

- **Regex on code without AST context** — prone to false positives in strings/comments
- **Too broad** — "all controllers must be perfect" is not checkable
- **Configuration-dependent** — checks should work without database/network access
- **Slow** — a check that takes >5 seconds will be skipped by developers
- **Environment-specific** — checks should run the same locally and in CI

## Exporting

```bash
make export-rules              # exports to ./gauntlet-export/
make export-rules OUT=/tmp/rules  # custom output
```

The export bundle includes all four layers and a README with installation instructions.
