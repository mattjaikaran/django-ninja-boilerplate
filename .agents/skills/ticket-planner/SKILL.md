---
name: ticket-planner
description: >
  Turns a feature, journey step, bug, spec or large ticket into tier small
  tickets in docs/tickets/ that a worker model can finish with no design
  decisions: clarifies open decisions with the human, splits the work into
  vertical slices, writes owns and Verify blocks, and passes
  scripts/tickets.py check. Use when you plan, write, split, scope or fix a
  ticket, fill the queue before a handoff, or answer a needs-planner draft PR,
  even when the user only says "break this down" or "plan the work".
---

# Ticket planner

You are the planner. You write tickets that a small local model can finish
with no exploration and no design decisions. The worker reads only the ticket
and the files in `owns`, so the ticket must hold every fact and decision.

Read first:

- `docs/tickets/README.md`: format, lifecycle, collision rules, hot files.
- `docs/tickets/TEMPLATE.md`: copy it for every new ticket.
- `docs/AGENT_HANDOFF.md`: roles, the overnight loop, stop rules.

## Pre-flight

Do these steps before you write a ticket file.

1. **Find the facts.** Read the journey, the feature, the code, and the open
   tickets (`uv run python scripts/tickets.py next --tier small`). Do not ask
   the human for anything the repo can tell you.
2. **Clarify the decisions.** List each open decision: behavior, status codes,
   permissions, data shape, scope edges. Ask the human in one numbered round.
   Give your recommended answer with each question, and word it so "yes"
   accepts the recommendation:

   ```text
   Q1. Another user's todo: return 404, as get_todo does? (Recommended: yes)
   Q2. Completing a completed todo: return 200 and change nothing? (Recommended: yes)
   ```

   Ask a second round only for questions that the answers opened. Stop when
   no decision is open. Do not write a ticket on a guess.
3. **Slice.** Split the work into vertical slices, then order them. Follow
   [references/slicing.md](references/slicing.md).
4. **Size.** Hold each slice against the tier small checklist below. Split
   again when a line fails.
5. **Confirm.** Show the human the numbered slice list: title, `depends_on`,
   and the behavior each delivers. Merge or split until they agree.

When the human is away, write `ready` tickets only for slices with no open
decision. Write the others with `status: blocked` and put the open question in
`## Context`.

## Write a ticket

[references/example-ticket.md](references/example-ticket.md) is a complete
tier small ticket. Match its shape.

1. Pick the next free number. Copy `docs/tickets/TEMPLATE.md` to
   `docs/tickets/T-NNN-short-slug.md`.
2. Set `id`, `title` and `branch: agent/T-NNN-short-slug`. The three prefixes
   must match.
3. Link the product spec. Put `J-NNN` in `journeys` and `F-NNN` in
   `features`. In `## Context`, name the journey file and step, for example
   `docs/product/journeys/J-001-sign-up-and-sign-in.md` step S2.
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
- Tests follow the testing policy in `AGENTS.md`: only for a bug fix, a
  changed public contract, or a boundary rule; at most one new test file.

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
