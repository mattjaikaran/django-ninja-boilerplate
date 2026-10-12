# Product spec: features and user journeys

This folder holds the product spec. It links each feature to the user
journeys that exercise it, and each journey step to the Playwright tests
that verify it. The JOURNEYS gate and the staff page at `/admin/journeys/`
read these files and the Playwright JSON report.

```
docs/product/
├── README.md            # this file: format and rules
├── FEATURES.md          # one line per feature
└── journeys/
    └── J-NNN-slug.md    # one file per journey
```

## Features file

`FEATURES.md` groups features under `## <Area>` headings. Write one feature
per line, exactly:

```
- [ ] F-001 Short feature title
- [x] F-002 Short feature title
```

- The line must match `^- \[( |x)\] (F-\d{3}) (.+)$`.
- `[x]` means "verified by a passing Playwright journey". It never means
  "the code exists".
- Do not use checkbox syntax for anything else in this file.

## Journey files

Name each file `journeys/J-NNN-slug.md`. The file name prefix must equal the
`id`. Start the file with YAML frontmatter, then write free prose (Goal,
Context, Notes).

```yaml
---
id: J-001
title: Sign up and sign in
actor: Visitor
status: building        # draft | building | done
steps:
  - id: S1
    title: Create an account
    story: As a visitor, I want to create an account, so that I can save my work.
    features: [F-001]
    acceptance:
      - The signup form returns me to the dashboard signed in.
known_issues:           # optional
  - step: S2
    ticket: T-004
    note: Login spinner never stops on slow networks.
---
```

- `id`, `title`, `actor`, `status`, and `steps` are required.
- Each step needs `id` (`S1`, `S2`, ...) and `title`. `story`, `features`,
  and `acceptance` are optional but expected.
- `known_issues` entries need `step` and `ticket`. The ticket file
  `T-NNN-*.md` must exist in `docs/tickets/`.

## Playwright tag convention

This repo ships only the backend API. The Playwright suite lives in the
frontend repo (in a mattstack project, `frontend/` beside `backend/`). The
React boilerplates do not ship Playwright yet: add `@playwright/test` and the
JSON reporter below when you add the frontend. Write one test per journey.
Tag it with the journey ID, and give each step a `test.step` whose title
starts with the step ID:

```ts
test('visitor signs up and signs in', { tag: '@J-001' }, async ({ page }) => {
  await test.step('J-001-S1: create an account', async () => {
    // ...
  });
  await test.step('J-001-S2: sign in', async () => {
    // ...
  });
});
```

The JSON report keeps each step's result, so the gate knows where the test
stopped. When `J-001-S2` fails, S1 is `verified`, S2 is `failing`, and later
steps are `no_result` because they did not run. Do not write a separate test
per step.

A test without step titles can carry step tags instead
(`tag: ['@J-001', '@J-001-S1']`); then every tagged step takes the test's
overall result. Tags written inline in test or `describe` titles also count.

Add the JSON reporter to `playwright.config.ts`, so the gate can read the
results:

```ts
export default defineConfig({
  reporter: [
    ['list'],
    ['json', { outputFile: 'test-results/journeys.json' }],
  ],
});
```

A test passes when every result has status `passed`, or the test status is
`expected`. Skipped tests count as no result.

## Paths

The gate and the admin page resolve the same paths:

| Env var | Default |
| ------- | ------- |
| `JOURNEYS_SPEC_DIR` | `<repo>/docs/product` |
| `JOURNEYS_E2E_DIR` | `<repo>/../frontend/e2e` (scans `**/*.spec.ts`, `**/*.spec.js`, `**/*.test.ts`) |
| `JOURNEYS_E2E_REPORT` | `<repo>/../frontend/test-results/journeys.json` |
| `TICKETS_DIR` | `<repo>/docs/tickets` |

## Step states

| State | Meaning |
| ----- | ------- |
| `verified` | Every tagged test passed in the report. |
| `failing` | A tagged test failed. |
| `documented` | Failing or missing, and listed in `known_issues`. |
| `no_result` | A tagged test exists, but the report is missing or has no result for it. |
| `no_spec` | No test carries the step tag. |

## Sync rules

Errors fail the JOURNEYS gate. Warnings and gaps do not.

| Level | Code | Rule |
| ----- | ---- | ---- |
| Error | `bad_frontmatter` | A journey file has missing or invalid frontmatter. |
| Error | `bad_feature_line` | A checkbox line in `FEATURES.md` does not match the format. |
| Error | `missing_features_file` | `FEATURES.md` cannot be read. |
| Error | `duplicate_id` | A feature, journey, or step ID is defined twice. |
| Error | `id_filename_mismatch` | The file name prefix is not the journey `id`. |
| Error | `unknown_feature` | A step references a feature that is not in `FEATURES.md`. |
| Error | `unknown_step` | A known issue references a step that does not exist. |
| Error | `missing_ticket` | A known issue references a ticket file that does not exist. |
| Error | `done_not_verified` | A `done` journey has a step that is not `verified`, or a failing `@J-NNN` test. |
| Error | `done_with_known_issues` | A `done` journey lists known issues. |
| Error | `feature_checked_unreferenced` | A `[x]` feature has no referencing step. |
| Error | `feature_checked_unverified` | A `[x]` feature has a referencing step that is not `verified`. |
| Error | `undocumented_failure` | A step is `failing` and no known issue covers it. |
| Error | `orphan_tag` | A test tag names a journey or step that does not exist. |
| Warning | `feature_ready` | A `[ ]` feature has every referencing step `verified`. Check it off. |
| Warning | `bad_report` | The Playwright JSON report cannot be parsed. |
| Gap | `no_spec`, `no_result` | A step of a `draft` or `building` journey has no test or no result. |

## Commands

```bash
uv run python scripts/check_journeys.py          # errors, warnings, gaps
uv run python scripts/check_journeys.py --json   # full report as JSON
```

Staff can open the same report at `/admin/journeys/` (Admin, Monitoring,
User Journeys).

## Sync loop for agents

Load the `journey-sync` skill (`.agents/skills/journey-sync/SKILL.md`)
before you change a feature, a journey, or a Playwright test. Then keep the
three in step:

1. **You add or change a feature.** Add or edit its line in `FEATURES.md`.
   Leave it `[ ]`. Reference it from a journey step, or add a step.
2. **You add or change a journey.** Edit the frontmatter and the prose. Use
   real routes and screens. Keep `status: building` until it is earned.
3. **You add or change a Playwright test.** Tag it `@J-NNN` and title its
   steps `J-NNN-S<n>: ...`. Remove step titles of steps you deleted, or the
   gate reports `orphan_tag`.
4. **You rename or remove a step.** Update the step tags in the tests, the
   `known_issues` entries, and any ticket that names the step.
5. Run the Playwright suite with the JSON reporter, then run
   `uv run python scripts/check_journeys.py`. Fix every error.

## How "done" is earned

- A step is done when its `test.step` (or every test tagged with it) passes
  in the report.
- Set a journey to `status: done` only when every step is `verified`, no
  `@J-NNN` test fails, and `known_issues` is empty.
- Check a feature `[x]` only when every step that references it is
  `verified`. The gate warns with `feature_ready` when you can.
- Never check a feature or close a journey because the code exists.

## Document a failure with a ticket

When a tagged test fails and you cannot fix it now:

1. Create a ticket `docs/tickets/T-NNN-slug.md`. Follow the format in
   `docs/tickets/`. List the journey in `journeys:` and the features in
   `features:`.
2. Add a `known_issues` entry to the journey:

   ```yaml
   known_issues:
     - step: S2
       ticket: T-004
       note: Login spinner never stops on slow networks.
   ```

3. Keep the journey `building`. The step becomes `documented` and the gate
   stops reporting `undocumented_failure`.
4. When the fix lands and the test passes, remove the `known_issues` entry
   in the same change.
