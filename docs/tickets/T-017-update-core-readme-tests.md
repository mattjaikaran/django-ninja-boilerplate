---
id: T-017
title: Update core/README.md test notes after the test prune
status: ready
tier: small
depends_on: [T-002, T-007]
owns:
  - core/README.md
shared: []
journeys: []
features: []
branch: agent/T-017-update-core-readme-tests
---
## Context

T-002 removes the Centrifugo client tests from `core/tests/test_centrifugo.py`.
T-007 removes the `TestUserModel` class from `core/tests/test_user.py`. After
both merge, `core/README.md` describes tests that no longer exist, and one of
its example commands selects a test that is gone. This ticket updates the
README text. It changes no code. The full plan is in
`docs/tickets/PRUNE_PLAN.md`.

Read only `core/README.md` (lines 52-57 and 157-185).

## Change

Line numbers match `core/README.md` when this ticket was written. If the lines
moved, find each line by its text.

1. In `core/README.md`, in the folder tree, replace the comment on the
   `test_centrifugo.py` line (line 56) so the line reads:

   ```text
   │   ├── test_centrifugo.py # Centrifugo connection token expiry test
   ```

2. In the `### Running Tests` code block, replace the two class and test
   examples (lines 166-170) with:

   ```bash
   # Run specific test class
   uv run pytest core/tests/test_user.py::TestUserAPI

   # Run specific test
   uv run pytest core/tests/test_user.py::TestUserAPI::test_get_user
   ```

3. Under `### Test Coverage`, replace the bullet list (lines 177-185) with:

   ```markdown
   - Signup, login, and passwordless login
   - Account and IP lockout
   - JWT refresh rotation and logout revocation
   - Route authentication and staff permissions
   - User admin API endpoints
   ```

## Do not

- Do not edit files outside `owns`.
- Do not add dependencies.
- Do not hand-edit generated files (`docs/openapi/openapi.json`, migrations,
  `uv.lock`). Regenerate them.
- Do not change any other section of `core/README.md`.
- Do not change code or tests.

## Verify

Run these after T-002 and T-007 are merged.

```bash
grep -n "TestUserModel" core/README.md
grep -n "token + client" core/README.md
```

Expected: no output from either command (exit code 1).

```bash
DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest core/tests/test_user.py::TestUserAPI::test_get_user -q --no-cov -p no:cacheprovider
```

Expected: `1 passed`. This proves the example command in the README works.

## Done when

- [ ] `core/README.md` names only tests that exist.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.
