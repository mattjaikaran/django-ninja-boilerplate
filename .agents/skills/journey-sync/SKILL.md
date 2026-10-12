---
name: journey-sync
description: >
  Use when you add or change a product feature, a user journey, or a
  Playwright e2e test, or when the JOURNEYS gate fails. Keeps
  docs/product/FEATURES.md, docs/product/journeys/*.md, and the @J-NNN test
  tags in sync. Use when the user mentions "journey", "feature list",
  "user story", "Playwright tag", "check off a feature", or "JOURNEYS gate".
---

# Journey sync

`docs/product/` links features to user journeys, and journey steps to the
Playwright tests that verify them. The JOURNEYS gate
(`scripts/check_journeys.py`) and the staff page `/admin/journeys/` read the
same files through `journeys/services/spec_service.py`.

The full format and every rule code live in `docs/product/README.md`. Read it
before your first edit.

## When to use this skill

- You add, rename, or remove a product feature.
- You add or change a journey or a journey step.
- You add, retag, or delete a Playwright test in the frontend.
- A tagged test fails and you cannot fix it in this change.
- The JOURNEYS gate reports an error.

## Sync checklist

1. **Feature.** One line in `FEATURES.md`: `- [ ] F-NNN Title`. New features
   start `[ ]`. Reference each feature from at least one journey step.
2. **Journey.** File `journeys/J-NNN-slug.md`. The file name prefix equals
   `id`. Write real routes and screens in the prose. Keep
   `status: building` until every step is verified.
3. **Test.** Write one Playwright test per journey, tagged `@J-NNN`. Wrap
   each step in `test.step('J-NNN-S<n>: ...')`. Do not write a test per
   step. Remove step titles of deleted steps, or the gate reports
   `orphan_tag`.
4. **Step rename or removal.** Update test tags, `known_issues`, and tickets
   that name the step in the same change.
5. **Failure you cannot fix now.** Create `docs/tickets/T-NNN-slug.md`, then
   add `known_issues: [{step: S<n>, ticket: T-NNN, note: ...}]` to the
   journey. Remove the entry when the test passes.
6. **Earn "done".** Check a feature `[x]` only when every step that references
   it is `verified`. Set a journey `done` only when every step is
   `verified`, no `@J-NNN` test fails, and `known_issues` is empty. Code
   that exists is not evidence.
7. **Verify.** Run the Playwright suite with the JSON reporter, then the
   gate. Fix every error. Gaps are allowed on `draft` and `building`
   journeys.

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
