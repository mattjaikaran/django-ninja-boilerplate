---
name: ticket-planner
description: >
  Use when writing, scoping, splitting or reviewing tickets in docs/tickets/
  for worker models, or preparing a handoff queue before the planner runs out
  of limits. Covers tier small rules, owns and shared paths, collision checks
  with scripts/tickets.py check, and links to journeys and features. Use when
  the user mentions "ticket", "T-NNN", "handoff", "queue", "worker model",
  "small model", or "tickets.py".
---

# Ticket planner

You are the planner. You write tickets that a small local model can finish
with no exploration and no design decisions.

## When to use this skill

- Turning a feature, journey step or bug into tickets
- Splitting a large ticket into small ones
- Filling the queue before a handoff
- Reviewing a worker PR that was rejected or stopped

## Read first

- `docs/tickets/README.md`: format, lifecycle, collision rules, hot files.
- `docs/tickets/TEMPLATE.md`: copy it for every new ticket.
- `docs/AGENT_HANDOFF.md`: roles, the overnight loop, stop rules.

## Write a ticket

1. Pick the next free number. Copy `docs/tickets/TEMPLATE.md` to
   `docs/tickets/T-NNN-short-slug.md`.
2. Set `id`, `title` and `branch: agent/T-NNN-short-slug`. The three prefixes
   must match.
3. Link the product spec. Put `J-NNN` in `journeys` and `F-NNN` in
   `features`. In `## Context`, name the journey file and step, for example
   `docs/product/journeys/J-001-sign-up.md` step S2.
4. List every path the PR may change in `owns`. Use exact files. Use a
   directory or glob only when the files do not exist yet.
5. List hot files in `shared` and in `owns`: `api/urls.py`,
   `docs/openapi/openapi.json`, `<app>/migrations/`, `pyproject.toml`,
   `uv.lock`, `CHANGELOG.md`, `api/settings/*`.
6. Write `## Change` as numbered steps, one file per step. Give exact function
   signatures or a snippet to adapt. Make every decision here.
7. Write `## Verify` as fenced commands, each with its expected output.
8. Delete the template comments. Set `status: ready`.
9. Run the gate:

   ```bash
   uv run python scripts/tickets.py check
   ```

## Tier small checklist

Mark a ticket `tier: small` only when every line holds. Otherwise use
`tier: large` and split it.

- One concern.
- About 200 changed lines or fewer.
- Exact file paths; all of them in `owns`.
- Exact signatures or snippets.
- No design decision left.
- Verify commands with expected output.
- No new dependency.
- No migration, unless the ticket says so and owns `<app>/migrations/`.

## Avoid collisions

- `check` fails when two `ready` tickets overlap in `owns` or `shared` and no
  `depends_on` path links them.
- Fix it one of two ways: merge the tickets, or add `depends_on` so they run
  in order.
- Two tickets that both add a migration to the same app must be ordered.
- Two tickets that both change the API contract must be ordered: both
  regenerate `docs/openapi/openapi.json`.

## Hand off

Before you stop, run:

```bash
uv run python scripts/tickets.py check
uv run python scripts/tickets.py next --tier small
```

Commit and push the ticket files to `main`. Follow the checklist in
`docs/AGENT_HANDOFF.md`, section "Handoff when the planner runs out of
limits".

## After a rejected or stopped PR

- Add one line to "When to add to this section" in `AGENTS.md`: what not to
  do, what to do instead, why.
- If the ticket was unclear, rewrite it. If the template allowed the gap,
  tighten `docs/tickets/TEMPLATE.md`.
- A draft PR labeled `needs-planner` means the worker stopped. Read its
  failure log, fix the ticket, then close the PR and delete the branch so the
  ticket is claimable again.
