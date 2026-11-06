---
id: T-018
title: Scope the public-read throttle from issue 45
status: draft
tier: large
depends_on: []
owns:
  - .context/EXAMPLES.md
  - api/settings/common.py
  - core/controllers/session_controller.py
  - core/features/controller.py
  - core/tests/test_throttling.py
shared:
  - api/settings/*
journeys: []
features: []
branch: agent/T-018-public-read-throttle
---
## Context

Issue #45 reports that public reads return 429 after a few page views because
they share the anonymous `100/day` budget. That premise is false for the
installed django-ninja-extra 0.31.4. `NINJA_EXTRA["THROTTLE_CLASSES"]` in
`api/settings/common.py` is the class list a bare `@throttle` (no arguments)
uses; it is not applied to a route on its own. A route is limited only when
its controller or handler names a throttle.

No route in this repo names `AnonRateThrottle`, so the `anon` rate limits
nothing, and 150 anonymous GET requests to the CSRF endpoint all returned
200. The contradiction came from `.context/EXAMPLES.md`, which said the class
list applied to every route; this spec corrects that.

The remaining question is a decision, not a bug fix: keep public reads
unthrottled, or give them an explicit scope. `owns` lists every path either
answer would touch.

## Change

1. Decide one of:
   - Close issue #45 as not a bug. The correction to `.context/EXAMPLES.md`
     already removed the false premise; no code changes.
   - Add a scoped limit for public reads, for example `anon-read` at
     `600/min`, and apply it to the public handlers in
     `core/controllers/session_controller.py` and
     `core/features/controller.py`.
2. If the limit is added, add the scope to
   `NINJA_EXTRA["THROTTLE_RATES"]` in `api/settings/common.py`, document it
   in the rate-limiting sections of `.context/EXAMPLES.md`, and add the
   proof in `core/tests/test_throttling.py`.
3. Split the chosen answer into a small ticket, or close this one with the
   decision recorded here.

## Do not

- Do not edit files outside `owns`.
- Do not add the limit before the decision above.
- Do not add dependencies.
- Do not hand-edit generated files (`docs/openapi/openapi.json`,
  migrations, `uv.lock`). Regenerate them.

## Verify

```bash
uv run pytest core/tests/test_throttling.py -q
```

Expected: the existing throttle tests pass. With the limit added, a test
sends 600 anonymous requests to each public read, sees 200, then 429 with a
`Retry-After` header.

## Done when

- [ ] The decision is recorded in this file.
- [ ] If the limit is added, every changed path is in `owns`.
- [ ] `just gauntlet-quick` passes.
