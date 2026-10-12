---
name: journey-sync
description: >
  Keeps docs/product/FEATURES.md, the journey specs in
  docs/product/journeys/, and the @J-NNN Playwright tags in the frontend repo
  in sync, and fixes JOURNEYS gate errors from scripts/check_journeys.py. Use
  when you add, rename or remove a feature, a journey or a journey step,
  change an API route that a journey step calls, add or retag a Playwright
  journey test, check off a feature, mark a journey done, or record a known
  issue.
---

# Journey sync

`docs/product/` links features to user journeys, and journey steps to the
Playwright tests that verify them. The JOURNEYS gate
(`scripts/check_journeys.py`) and the staff page `/admin/journeys/` read the
same files through `journeys/services/spec_service.py`.

The full format and every rule code live in `docs/product/README.md`. Read it
before your first edit.

## This repo is backend-only

- This repo has no frontend and no Playwright tests. The Playwright journey
  tests live in the frontend repo, built from the maintainer's React
  boilerplates.
- In this repo, you edit `docs/product/FEATURES.md`, the journey files, and
  `docs/tickets/`. You change a Playwright test in the frontend repo.
- The gate reads the tests from `JOURNEYS_E2E_DIR` (default
  `../frontend/e2e`) and the results from `JOURNEYS_E2E_REPORT` (default
  `../frontend/test-results/journeys.json`). When it prints
  `e2e dir ... (missing)`, point these variables at the frontend checkout.
- When a backend change alters a route, status code, or response that a
  journey step calls, update the journey's `## Context` here and change the
  journey test in the frontend repo.

## Playwright tag rule

Write one test per journey, tagged `@J-NNN`. Wrap each step in
`test.step('J-NNN-S<n>: ...')`. Do not write a test per step.

```ts
test('visitor signs up and signs in', { tag: '@J-001' }, async ({ page }) => {
  await test.step('J-001-S1: create an account', async () => { /* ... */ });
  await test.step('J-001-S2: sign in', async () => { /* ... */ });
});
```

## Sync checklist

1. **Feature.** One line in `FEATURES.md`: `- [ ] F-NNN Title`. New features
   start `[ ]`. Reference each feature from at least one journey step.
2. **Journey.** File `journeys/J-NNN-slug.md`. The file name prefix equals
   `id`. Write real routes and screens in the prose. Keep
   `status: building` until every step is verified.
3. **Test.** Follow the tag rule above. Remove the step titles of deleted
   steps, or the gate reports `orphan_tag`.
4. **Step rename or removal.** Update test step titles, `known_issues`, and
   tickets that name the step in the same change.
5. **Failure you cannot fix now.** Create `docs/tickets/T-NNN-slug.md`, then
   add `known_issues: [{step: S<n>, ticket: T-NNN, note: ...}]` to the
   journey. Remove the entry when the test passes.
6. **Earn "done".** Check a feature `[x]` only when every step that references
   it is `verified`. Set a journey `done` only when every step is
   `verified`, no `@J-NNN` test fails, and `known_issues` is empty. Code
   that exists is not evidence.
7. **Verify.** In the frontend repo, run the Playwright suite with the JSON
   reporter. Then run the gate here. Fix every error. Gaps are allowed on
   `draft` and `building` journeys.

## Commands

```bash
uv run python scripts/check_journeys.py          # errors, warnings, gaps
uv run python scripts/check_journeys.py --json   # full report as JSON
```

Override the paths with `JOURNEYS_SPEC_DIR`, `JOURNEYS_E2E_DIR`,
`JOURNEYS_E2E_REPORT`, and `TICKETS_DIR`.

Staff view: `/admin/journeys/` (Admin, Monitoring, User Journeys). Each
journey has a detail page at `/admin/journeys/J-NNN/` that shows what is
missing at every step.
