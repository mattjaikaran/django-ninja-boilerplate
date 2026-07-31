---
name: code-review
description: Two-axis review (Standards + Spec) of changes since a fixed point. Runs parallel sub-agents — one checks repo conventions, the other checks the spec. Use when user wants to review a branch, PR, WIP changes, or asks "review since X".
---

Two-axis review of the diff between `HEAD` and a fixed point:

- **Standards** — does the code follow this repo's conventions? (rule://backend-conventions, rule://django-ninja-anti-patterns, CLAUDE.md)
- **Spec** — does the code implement what was asked?

## Process

### 1. Pin the fixed point

Whatever the user says — commit, branch, tag, `main`. Default: `main` if unspecified.

Confirm: `git diff <fixed>...HEAD` is non-empty. Fail here, not in sub-agents.

### 2. Standards sources (always apply)

This repo's standards are:
- `rule://backend-conventions` — framework identity, decorator order, naming, layer architecture
- `rule://django-ninja-anti-patterns` — 12 common AI mistakes with wrong/right examples
- `CLAUDE.md` — gauntlet gates, architecture rules, definition of done
- `scripts/check_conventions.py` — 12 deterministic convention checks (run it!)

Plus the **smell baseline** — Fowler code smells that apply regardless of docs:

- **Mysterious Name** — name doesn't reveal what it does → rename it
- **Duplicated Code** — same logic in multiple hunks → extract
- **Feature Envy** — method reaches into another object's data → move it
- **Data Clumps** — same params always travel together → bundle into type
- **Primitive Obsession** — primitive standing in for domain concept → give it a type
- **Repeated Switches** — same if-cascade on same type recurs → polymorphism or map
- **Shotgun Surgery** — one change scattered across many files → gather into module
- **Divergent Change** — one file edited for unrelated reasons → split
- **Speculative Generality** — abstraction for needs that don't exist → delete it
- **Message Chains** — long `a.b().c().d()` → hide behind method
- **Middle Man** — class that mostly delegates → cut it
- **Refused Bequest** — subclass ignores most of what it inherits → drop inheritance

Skip anything that `ruff`, `mypy`, `bandit`, or `check_conventions.py` already enforces.

### 3. Standards review

Run `uv run python scripts/check_conventions.py` first. Then review the diff manually against the conventions docs and smell baseline. Report per-file where the diff violates a documented standard or exhibits a smell.

### 4. Spec review

If no spec/issue is referenced, skip. Otherwise verify:
- Requirements asked for that are missing or partial
- Behavior added that wasn't asked for (scope creep)
- Requirements that look implemented but wrong

### 5. Report

Two sections: `## Standards` and `## Spec`. End with count per axis and worst issue per axis.
