# User journeys

The `journeys` app shows how far each user journey is tested. Open it at
**Admin, Monitoring, User Journeys** (`/admin/journeys/`).

The index page shows one card for each journey. The summary counts the
journeys per status and shows how many have both a backend and a browser
test. Each card shows its status, its step progress, the test files it
finds, and its endpoints. Use the search box to filter by ID, title, surface,
story, or endpoint. Use the status chips to show one status only.

A journey with a file in `docs/product/journeys/` also has a detail page at
`/admin/journeys/J-NNN/`. A collapsed **Feature spec sync** section on the
index shows the features, the journey steps, and the sync findings.

## The journey table

The table comes from the journeys table of `docs/product/journeys.md`: a
Markdown table whose first column is `ID` (`J-01` or `J-001`) and whose other
columns are matched by header words: `Journey`, `Stories`, `Backend surface`,
`Smoke test`, and `Playwright`. Write endpoints in code ticks as
`GET /api/x`, the Playwright spec as `e2e/jNN-name.spec.ts`, and a smoke test
as `tests/smoke/test_jNN_name.py`. When the table names no smoke test, the page
looks for `tests/smoke/test_jNN_*.py` and lists the `/api/...` paths that file
calls.

Status comes from the files, not from a field you set:

| Status | Meaning |
| ------ | ------- |
| Backend and browser tests | A smoke test and a Playwright spec both exist. |
| Backend test only | A smoke test exists; the Playwright spec does not. |
| Browser test only | A Playwright spec exists; no smoke test does. |
| Not started | Neither exists. |

The table is read-only. It is not a sync rule, so the JOURNEYS gate ignores
it.

## The detail page

The detail page shows the steps as a connected flow. Each node color shows the
evidence state of its step:

| Color | State | Meaning |
| ----- | ----- | ------- |
| Green | Verified | The step passed in the last report. |
| Red | Failing | The last report shows a failing test, and no known issue covers it. |
| Amber | Known issue | A `known_issues` entry covers a step that did not pass. |
| Blue | Not run | A test covers the step, but the last report has no result for it. |
| Grey | No test | No test covers the step. |

Expand a step to see its story, its acceptance criteria, its linked features
(F-NNN), and its test evidence. Use **Expand all** and **Collapse all** to
change every step at once. A link with a step ID in the fragment, such as
`#J-001-S2`, opens that step.

## What it reads

- `docs/product/FEATURES.md` and `docs/product/journeys/*.md`. The format and
  the sync rules are in [docs/product/README.md](../docs/product/README.md).
- The journeys table. Set `JOURNEYS_INDEX_FILE` when it is not at
  `docs/product/journeys.md` (here or in the repository root `docs/`).
- The backend smoke tests. Set `JOURNEYS_SMOKE_DIR` when they are not in
  `tests/smoke/`.
- The frontend Playwright sources and JSON report. Set `JOURNEYS_E2E_DIR`
  and `JOURNEYS_E2E_REPORT` when the frontend is not at `../frontend`.

`JOURNEYS_ENABLED` turns the pages, the sidebar link and the dashboard card
on or off. It defaults to on, and `api.settings.prod` turns it off because
the production image does not include `docs/`.

## How it works

- `services/spec_service.py` parses the spec and applies the sync rules.
- `services/journey_index.py` reads the journeys table and checks the test
  files it names.
- `services/e2e_evidence.py` reads test tags and Playwright results.
- `services/spec_models.py` holds the paths and the data classes.
- `views.py` renders two staff-only pages. The pages load
  `static/journeys/journeys.js` and `journeys.css`. They use no inline script
  or style, so the production CSP holds.

The services import no Django, so `scripts/check_journeys.py` (the JOURNEYS
gate) runs the same rules without settings:

```bash
uv run python scripts/check_journeys.py
```

The app has no models and no migrations.
