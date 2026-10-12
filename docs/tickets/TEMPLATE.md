---
id: T-NNN
title: Imperative summary, under 70 characters
status: draft           # draft | ready | blocked | done
tier: small             # small | large
depends_on: []          # ticket IDs that must be done first, e.g. [T-001]
owns:                   # every path or glob this PR may change; nothing else
  - path/to/file.py
shared: []              # hot files this PR touches: api/urls.py,
                        # docs/openapi/openapi.json, <app>/migrations/,
                        # pyproject.toml, uv.lock, CHANGELOG.md, api/settings/*
journeys: []            # e.g. [J-001]
features: []            # e.g. [F-001]
branch: agent/T-NNN-short-slug
---
<!--
Copy this file to docs/tickets/T-NNN-short-slug.md. Use the next free number.
The id, the file name prefix, and the branch prefix must match.
Delete every HTML comment before you set status: ready.

A ticket is tier: small only when all of these hold:
- It has one concern. One bug, one endpoint, one test file, one doc.
- The diff is at most about 200 changed lines.
- It names the exact file paths. Every changed path is listed in owns.
- It gives the exact function signatures, or a code snippet to adapt.
- It needs no design decision. The planner made every decision already.
- ## Verify has commands and states their expected output.
- It adds no new dependency.
- It adds no migration, unless the ticket says so and lists
  <app>/migrations/ under owns and shared.
If any of these fails, use tier: large. A worker model never takes a large
ticket. Split it into small tickets, or the planner does it.

Then run: uv run python scripts/tickets.py check
-->

## Context

<!--
Why this change exists, in two to five sentences. Link the journey, step, or
feature: docs/product/journeys/J-NNN-slug.md (S2), F-NNN.
Name the files the worker must read. Keep it to the files in owns, plus at
most two read-only references with line ranges.
-->

## Change

<!--
Numbered steps. One file per step. Exact paths, exact names.

1. In `path/to/service.py`, add this method to `ThingService`:

   ```python
   def archive(self, user: User, thing_id: str) -> Thing:
       ...
   ```

2. In `path/to/controller.py`, add `POST /things/{thing_id}/archive` that
   calls `ThingService.archive` and returns `200, ThingSchema`.
-->

## Do not

<!--
Things the worker must not do. Always keep the first three lines.
-->

- Do not edit files outside `owns`.
- Do not add dependencies.
- Do not hand-edit generated files (`docs/openapi/openapi.json`, migrations,
  `uv.lock`). Regenerate them.

## Verify

<!--
Commands the worker runs, each with its expected result. A small ready
ticket must have at least one fenced command block here.
-->

```bash
uv run pytest path/to/tests/test_thing.py -q
```

Expected: all tests pass, `0 failed`.

## Done when

<!--
Observable outcomes. The worker's PR also sets status: done in this file.
-->

- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, plus `status: done` in this file.
