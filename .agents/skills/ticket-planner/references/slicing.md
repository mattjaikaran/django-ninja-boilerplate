# Slice work into tickets

Read this when you split a feature, journey, spec or large ticket into tier
small tickets.

## Vertical slices

A slice is one behavior a user or client can observe, cut through every layer
this repo owns: model and migration (only if needed), service, schema,
controller, the one test the testing policy asks for, and the regenerated
`docs/openapi/openapi.json`. A merged slice works on its own: a request
against the API proves it.

- Map each slice to a journey step: one acceptance line of `J-NNN` S<n>, or a
  small group of them. Put the step in the ticket's `## Context`.
- Slice by behavior, not by layer. A ticket for "all the models" or "all the
  services" proves nothing alone, and every later ticket waits for it.
- This repo is backend-only. The screens and the Playwright test for a step
  live in the frontend repo. A ticket here owns only paths in this repo, so the
  slice ends at the API contract.
- Prefactor first. When a slice is easy only after a move or a rename, make
  that its own ticket and list it in `depends_on`.

## Order the slices

- Write the slices as a numbered list: title, `depends_on`, and the behavior
  it delivers. Blockers come first.
- Slices that change the API contract all regenerate
  `docs/openapi/openapi.json`. Chain them with `depends_on`, or merge them.
- Slices that add a migration to the same app must be ordered.
- A slice with no blockers can run as soon as it is `ready`.

## Wide refactors

A rename or retype that breaks call sites across many apps cannot land as one
green slice. Use expand and contract:

1. Expand: one ticket adds the new form next to the old one. Nothing breaks.
2. Migrate: one ticket per app (or per directory) moves its call sites to the
   new form. Each depends on the expand ticket. The gauntlet stays green
   because the old form still exists.
3. Contract: one ticket deletes the old form. It depends on every migrate
   ticket.

## Size for a small model

The worker reads only the ticket and the files in `owns`. Split again when any
of these is true:

- The ticket has more than one concern.
- The diff is more than about 200 changed lines.
- The worker must read more than the files in `owns` plus two read-only
  references with line ranges.
- A step says "choose", "decide", "if needed", "as appropriate", "etc.", or
  "similar to". Make the decision and write it down instead.
- A step changes more than one file.

When a slice is still too big, split it by behavior: one endpoint, or one rule
of an endpoint (for example, the 404 for another user's object). Do not split
it by layer.

## Tests in a slice

Follow the testing policy in `AGENTS.md`. A slice gets a test only when it
fixes a bug, changes a public contract, or adds a boundary or permission rule.

- Name the test file and each assertion in `## Change`.
- Use at most one new test file per ticket.
- Test through the API (status code, response body, database state). Do not
  ask for unit tests per function, model tests, or tests that assert on mocks.
- Do not plan a red-green cycle per function. The worker proves the slice with
  the commands in `## Verify`.
