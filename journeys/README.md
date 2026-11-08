# User journeys

The `journeys` app shows how far each user journey is tested. Open it at
**Admin, Monitoring, User Journeys** (`/admin/journeys/`).

The page opens with one table row per journey: its status, the backend smoke
test and the Playwright browser test (each marked found or missing, with the
last Playwright result), the API endpoints it uses, and links. Below the table,
a collapsed **Feature spec sync** section shows the features, the journey steps,
and the sync findings. A journey that has a file in `docs/product/journeys/`
also has a step page at `/admin/journeys/J-NNN/`.

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
- `views.py` renders two staff-only pages. No inline script or style.

The services import no Django, so `scripts/check_journeys.py` (the JOURNEYS
gate) runs the same rules without settings:

```bash
uv run python scripts/check_journeys.py
```

The app has no models and no migrations.
