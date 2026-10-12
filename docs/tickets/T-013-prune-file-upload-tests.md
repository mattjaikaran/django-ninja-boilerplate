---
id: T-013
title: Prune model and duplicate tests from files/tests/test_files.py
status: done
tier: small
depends_on: []
owns:
  - files/tests/test_files.py
shared: []
journeys: []
features: []
branch: agent/T-013-prune-file-upload-tests
---
## Context

The testing policy in `AGENTS.md` (section 10) keeps smoke, auth, permission, ownership, API contract, regression and security tests. It cuts model field and `__str__` tests, tests that assert on mocks, settings-default tests, schema echo, and tests that duplicate an API-level test. This ticket deletes 8 test functions from `files/tests/test_files.py` that fall in the cut list. The full plan is in `docs/tickets/PRUNE_PLAN.md`.

**Kept on purpose.** The ownership test (`test_confirm_wrong_user_raises`), the key namespacing test (`test_custom_folder`), the confirmed-only listing test, the API tests, and every `TestUploadValidation` test stay. The validation tests guard size limits, content types, magic bytes and path traversal.

Read only `files/tests/test_files.py`. You need no other file.

|Test to delete|Why it goes|
|---|---|
|`TestFileUploadModel::test_create_file_upload`|Model field and `__str__` test.|
|`TestFileUploadModel::test_s3_url_none_when_not_confirmed`|Model property unit test.|
|`TestFileUploadModel::test_ordering_newest_first`|Model `Meta.ordering` test.|
|`TestGeneratePresignedUrl::test_local_dev_fallback`|Duplicate of `TestFilesAPI::test_presigned_url_endpoint` plus the traversal test.|
|`TestGeneratePresignedUrl::test_filename_sanitized`|Duplicate of `TestUploadValidation::test_traversal_filename_never_reaches_storage_key`, which is stricter.|
|`TestConfirmUpload::test_confirm_sets_flags`|Duplicate of `TestFilesAPI::test_confirm_upload_endpoint`.|
|`TestConfirmUpload::test_confirm_without_size`|Service unit test of an optional argument.|
|`TestListFiles::test_list_all_includes_unconfirmed`|Service unit test of a query flag.|

## Change

Line numbers match `files/tests/test_files.py` when this ticket was written. If the lines moved, find each test by name.

1. In `files/tests/test_files.py`, delete these blocks. Include the decorators above each block.
   - The whole class `TestFileUploadModel` (lines 41-78). Every test in it goes: `test_create_file_upload`, `test_s3_url_none_when_not_confirmed`, `test_ordering_newest_first`.
   - `TestGeneratePresignedUrl::test_local_dev_fallback` (lines 88-106).
   - `TestGeneratePresignedUrl::test_filename_sanitized` (lines 108-116).
   - `TestConfirmUpload::test_confirm_sets_flags` (lines 135-147).
   - `TestConfirmUpload::test_confirm_without_size` (lines 149-155).
   - `TestListFiles::test_list_all_includes_unconfirmed` (lines 198-205).
2. Delete the `# Model tests` section comment block above `TestFileUploadModel` (lines 36-38).
3. Keep two blank lines between top-level blocks and one blank line between methods. If spacing is wrong, run `uv run ruff format files/tests/test_files.py`. Do not run it on other files.

## Do not

- Do not edit files outside `owns`.
- Do not add dependencies.
- Do not hand-edit generated files (`docs/openapi/openapi.json`, migrations,
  `uv.lock`). Regenerate them.
- Do not change non-test code.
- Do not rewrite, rename, or reorder the kept tests.
- Do not add tests.
- Do not delete a test, fixture, import, or comment that this ticket does not name.

## Verify

```bash
FILES_ENABLED=true DJANGO_SETTINGS_MODULE=api.settings.test uv run pytest files/tests/test_files.py -q --no-cov -p no:cacheprovider
```

Expected: `21 passed` (no failures, no errors). The `files` app is optional, so the command sets `FILES_ENABLED=true`. Without it, collection fails with a `RuntimeError` because the app is not in `INSTALLED_APPS`.

```bash
uv run ruff check files/tests/test_files.py
uv run ruff format --check files/tests/test_files.py
grep -cE '^ *def test_' files/tests/test_files.py
```

Expected: `All checks passed!`, then `1 file already formatted`, then `14`. The ruff config sets `fix = true`. If `ruff check` reports fixed errors, it changed the file: review the diff, then run it again until it prints `All checks passed!`.

## Done when

- [ ] The 8 tests in the table under Context are gone, and 14 test functions remain.
- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, and it sets `status: done` in this ticket file.
