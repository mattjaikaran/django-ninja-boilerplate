# Gauntlet Adoption Prompt

Copy this entire message and send it to your AI coding assistant (Claude Code, Cursor, Copilot, etc.) in any codebase to install the four-layer gauntlet defense.

---

## Instructions for the AI

I need you to install a four-layer convention enforcement system (the "gauntlet") in this codebase. Here's exactly what to build, in order:

### Step 1: Document Existing Conventions

First, map this codebase. Identify:
- What framework(s) are used? (Django Ninja? React? FastAPI? Next.js?)
- What are the naming conventions? (PascalCase components? snake_case files?)
- What patterns does the codebase consistently follow?
- What are the top 5-10 things an AI assistant would get wrong in this codebase?

Write these down as a `CLAUDE.md` (or `AGENTS.md`) at the project root.

### Step 2: Create the Four-Layer Defense

Create these files:

**Layer 1 — `.omp/APPEND_SYSTEM.md`**
A short document injected into every AI session. Contains:
- Framework identity: "This is X, NOT Y"
- The top 5-10 prohibited patterns the model will drift toward
- Correct alternatives for each
- Reference to rule files for details
- Keep it under 100 lines — the model reads this every turn

**Layer 2 — `.omp/rules/<framework>-conventions.md`** (with `alwaysApply: true`)
Full convention reference. Contains:
- Complete naming conventions table
- File structure template
- Layer/architecture contracts
- Component/endpoint patterns with wrong/right examples
- Frontmatter: `alwaysApply: true`, `globs` matching your source files

**Layer 2b — `.omp/rules/<framework>-anti-patterns.md`** (with `alwaysApply: true`)
Anti-pattern reference. For each anti-pattern:
- Show WRONG code (what the AI produces)
- Show CORRECT code (what it should produce)
- 10-15 anti-patterns minimum
- Real examples from your framework's domain

**Layer 3 — `.omp/rules/ttsr-<framework>-anti-patterns.md`**
Mid-generation interrupt rules. Frontmatter:
```yaml
---
description: Interrupts when model generates prohibited patterns
condition:
  - "from wrong_framework"
  - "bad_pattern_regex"
interruptMode: always
scope:
  - "tool:edit(**/*.<ext>)"
  - "tool:write(**/*.<ext>)"
---
```
Body: for each trigger, show the STOP message with correct alternatives.

**Layer 4 — `scripts/check_conventions.<ext>`**
A deterministic convention checker. Requirements:
- Under 600 lines
- Each check is a function that yields violations
- Exit 0 = pass, exit 1 = violations found
- Checks should include (adapt to your language):
  1. Wrong framework imports
  2. Wrong base class usage
  3. Missing decorators/hooks
  4. Business logic in wrong layer
  5. Redeclared inherited fields/members
  6. Unscoped queries/access
  7. Missing exports
  8. Wrong package manager usage
  9. Mocked infrastructure in tests
  10. Console.log/print in production code
  11. Any/as-casts/ts-ignore (for typed languages)
  12. Hardcoded credentials

### Step 3: Register in the Gauntlet Orchestrator

If the project has a Makefile or similar:
- Add `check-conventions` target
- Add `gauntlet` target that chains all gates
- Add to pre-commit hooks
- Add to CI workflow

If using `package.json`:
- Add `check-conventions` script
- Add `gauntlet` and `gauntlet:quick` scripts

### Step 4: Verify

After building everything:
1. Run the convention checker against the codebase
2. Fix any violations it finds (these are REAL bugs the AI let through)
3. Run the full gauntlet: `make gauntlet-quick`
4. Verify 0 violations

### Critical Rules

1. **Match existing patterns.** Read the codebase before writing ANY enforcement rule. Rules must reflect actual conventions, not what you think they should be.
2. **Zero false positives.** If the checker says it's wrong, it IS wrong. No "maybe" violations.
3. **Keep it small.** Each checker under 600 lines. Each rule under 200 lines.
4. **Deterministic.** Same input → same output. No flaky heuristics.
5. **Framework-specific.** Rules should mention actual framework names, class names, import paths from this codebase.

### Reference Implementation

For a complete working example, see the `django-ninja-boilerplate` project. It has:
- `.omp/APPEND_SYSTEM.md` — guardrails
- `.omp/rules/backend-conventions.md` — always-apply conventions
- `.omp/rules/django-ninja-anti-patterns.md` — 12 anti-patterns
- `.omp/rules/ttsr-framework-identity.md` — mid-generation interrupts
- `.omp/rules/ttsr-convention-violations.md` — mid-generation interrupts
- `scripts/check_conventions.py` — 12 AST/regex checks
- `scripts/check_cross_stack.py` — cross-stack checks
- `scripts/gauntlet.py` — orchestrator

The frontend counterpart is in `react-vite-boilerplate` with equivalent TypeScript checkers.
