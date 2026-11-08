---
id: T-019
title: Document the API versioning policy from issue 50
status: done
tier: small
depends_on: []
owns:
  - CHANGELOG.md
  - README.md
  - api/urls.py
  - docs/ARCHITECTURE.md
  - docs/openapi/openapi.json
  - scripts/release.py
  - tests/contract/test_openapi_contract.py
shared:
  - CHANGELOG.md
  - api/urls.py
  - docs/openapi/openapi.json
journeys: []
features: []
branch: agent/T-019-api-versioning-policy
---
## Context

Issue #50 asks for the API versioning policy in the docs and for the OpenAPI
`info.version` to report the release version. The policy is already true in
the code: the API mounts once at api/urls.py:70-95, and
`TestSingleUnversionedApi` in `tests/contract/test_route_access.py` asserts
that the /api/v1/ and /api/v2/ prefixes return 404. Release 1.13.0 removed
the inactive versioning module. The one code gap is the hardcoded
`version="0.1"` in `api/urls.py:80`; the `VERSION` file holds 1.14.0.

This ticket replaces the spec that agent-run gave issue #50. The first
attempt (PR #60) was rejected: it restyled about 40 released CHANGELOG lines
and unrelated README and ARCHITECTURE lines so that an external docs check
passed. That check reads every backticked token as a repo path, so a
backticked route such as /api/v1/ fails it. The rule here: new prose writes
API URL paths as plain text, every backticked path must exist, and no
existing line changes to satisfy the check.

The spec-gap issue #61 also names api/versioning.py. That file was deleted in
1.13.0 and nobody recreates it, so it is not owned. The missing ownership was
CHANGELOG.md and docs/ARCHITECTURE.md, which the versioning text needs.

## Change

1. In `api/urls.py`, add `from pathlib import Path` after `import re`, add
   this helper after `_docs_enabled = settings.API_DOCS != "off"`, and pass it
   as `version=`:

   ```python
   def _release_version() -> str:
       """The release version from the canonical ``VERSION`` file."""
       return (Path(settings.BASE_DIR) / "VERSION").read_text(encoding="utf-8").strip()
   ```

   ```python
   version=_release_version(),
   ```

2. In `tests/contract/test_openapi_contract.py`, add `from pathlib import
   Path` and `from django.conf import settings`, then add this test to
   `TestOpenAPIContract`, after `test_versioned_paths_are_absent`:

   ```python
   def test_info_version_is_the_release_version(self):
       """The OpenAPI version is the ``VERSION`` file's release version."""
       version_file = Path(settings.BASE_DIR) / "VERSION"
       expected = version_file.read_text(encoding="utf-8").strip()
       assert api.get_openapi_schema()["info"]["version"] == expected
   ```

3. In `README.md`, insert a new section between the API Documentation
   bullet list and the OpenAPI Tools heading:

   ```markdown
   ### API Versioning

   The API mounts once at /api/ with no version in the path. That surface is
   v1. It does not move when the project version changes, and there is no
   /api/v1/ alias. A breaking v2 ships beside it at /api/v2/; /api/ keeps
   serving v1 until it is retired. Contract tests assert that both versioned
   prefixes return 404 (`tests/contract/test_route_access.py`) and that the
   OpenAPI document lists no versioned paths
   (`tests/contract/test_openapi_contract.py`).

   The OpenAPI `info.version` is the release version from the `VERSION` file,
   so a generated client can tell which build published the schema.
   ```

4. In `docs/ARCHITECTURE.md`, insert a `### Versioning` subsection directly
   after the `## API Design` heading and before `### Endpoint Structure`:

   ```markdown
   ### Versioning

   The API mounts exactly once, at /api/, and paths carry no version. The
   unversioned surface is v1: it does not move when the project release
   version changes, and /api/v1/ is not mounted. A breaking change ships as
   /api/v2/ beside it; /api/ continues to serve v1 until it is retired. The
   inactive versioning module and its switch were removed in 1.13.0 and are
   not coming back.

   `tests/contract/test_route_access.py` asserts that the /api/v1/ and
   /api/v2/ prefixes return 404, and `tests/contract/test_openapi_contract.py`
   asserts that no versioned path reaches the OpenAPI document.

   `info.version` in the OpenAPI document is the release version read from
   the `VERSION` file. It identifies the build that produced the schema, not
   the route version.
   ```

5. In `CHANGELOG.md`, append a `### Changed` section under `## [Unreleased]`:

   ```markdown
   ### Changed
   - OpenAPI `info.version` now reports the release version from the `VERSION` file instead of the hardcoded `0.1`, so a generated client can identify the build that published the schema.
   - Documented the API versioning policy in `README.md` and `docs/ARCHITECTURE.md`: the API mounts once at /api/ as v1 with no version prefix, and a breaking v2 ships at /api/v2/ while /api/ keeps serving v1.
   ```

6. Regenerate the committed contract with `just openapi`. Only
   `docs/openapi/openapi.json` changes, and only its `info.version` value
   becomes 1.14.0.

## Do not

- Do not edit files outside `owns`.
- Do not edit a released CHANGELOG section (1.14.0 and older). Append only
  under Unreleased.
- Do not restyle existing README or ARCHITECTURE lines. A pre-existing
  citation that the docs gate flags belongs to issue #51, not this ticket.
- Do not backtick an API URL path in the new prose; write it plain.
- Do not hand-edit `docs/openapi/openapi.json`; regenerate it.
- Do not add dependencies or change behavior outside `info.version`.

## Verify

```bash
uv run python -m pytest tests/contract/test_openapi_contract.py -q
just openapi-check
uv run python scripts/tickets.py check
git diff --check origin/main...HEAD
```

Expected: 13 tests pass in `tests/contract/test_openapi_contract.py` (the 12
collected today plus `test_info_version_is_the_release_version`), the OpenAPI
contract is current and schema parity passes, and the tickets check passes.
Finish with `just gauntlet-quick`; on a host whose `just` cannot evaluate the
justfile, run
`uv run --python 3.13 --extra dev python scripts/gauntlet.py --quick --verbose`
instead and say so in the PR body.

## Done when

- [ ] The README and ARCHITECTURE sections above are present, and no other
      line of either file changed.
- [ ] `info.version` comes from the `VERSION` file, and the new contract test
      compares the two.
- [ ] `docs/openapi/openapi.json` is regenerated and `just openapi-check`
      passes.
- [ ] The PR changes only paths in `owns`, plus `status: done` in this file.
