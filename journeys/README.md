# User journeys

The `journeys` app shows how far each product feature is verified by
Playwright journeys. Open it at **Admin, Monitoring, User Journeys**
(`/admin/journeys/`). Each journey has a detail page at
`/admin/journeys/J-NNN/`.

## What it reads

- `docs/product/FEATURES.md` and `docs/product/journeys/*.md`. The format and
  the sync rules are in [docs/product/README.md](../docs/product/README.md).
- The frontend Playwright sources and JSON report. Set `JOURNEYS_E2E_DIR`
  and `JOURNEYS_E2E_REPORT` when the frontend is not at `../frontend`.

`JOURNEYS_ENABLED` turns the pages, the sidebar link and the dashboard card
on or off. It defaults to on, and `api.settings.prod` turns it off because
the production image does not include `docs/`.

## How it works

- `services/spec_service.py` parses the spec and applies the sync rules.
- `services/e2e_evidence.py` reads test tags and Playwright results.
- `services/spec_models.py` holds the paths and the data classes.
- `views.py` renders two staff-only pages. No inline script or style.

The services import no Django, so `scripts/check_journeys.py` (the JOURNEYS
gate) runs the same rules without settings:

```bash
uv run python scripts/check_journeys.py
```

The app has no models and no migrations.
