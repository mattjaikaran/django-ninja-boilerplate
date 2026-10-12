# Worked example: one vertical slice

This ticket is an example. The endpoint does not exist in the repo. Copy the
shape, not the content.

Why it is `tier: small`: one behavior (complete a todo), one step per file,
exact signatures, a decided status code for another user's todo, one test file
that the testing policy allows (an ownership rule), and Verify commands with
expected output. The OpenAPI file and the changelog are hot files, so they are
in `owns` and in `shared`.

````markdown
---
id: T-042
title: Add POST /todos/{todo_id}/complete
status: ready
tier: small
depends_on: []
owns:
  - todos/services/todo_service.py
  - todos/controllers/todo_controller.py
  - todos/tests/test_complete_todo.py
  - docs/openapi/openapi.json
  - CHANGELOG.md
shared:
  - docs/openapi/openapi.json
  - CHANGELOG.md
journeys: [J-002]
features: [F-010]
branch: agent/T-042-complete-todo
---

## Context

J-002 S3 (`docs/product/journeys/J-002-manage-todos.md`) needs a one-call way
to mark a todo complete. Another user's todo returns 404, as in `get_todo`.
Read only the files in `owns`.

## Change

1. In `todos/services/todo_service.py`, add this method to `TodoService`,
   after `update_todo`:

   ```python
   def complete_todo(self, todo_id: str, user: Any) -> Todo:
       todo = self.get_todo(todo_id, user)
       todo.completed = True
       todo.save(update_fields=["completed", "updated_at"])
       return todo
   ```

2. In `todos/controllers/todo_controller.py`, add this route after
   `update_todo`:

   ```python
   @http_post("/{todo_id}/complete", response={200: TodoSchema, 404: dict})
   @log_api_call()
   def complete_todo(self, request, todo_id: str):
       return 200, self.service.complete_todo(todo_id, request.user)
   ```

3. Create `todos/tests/test_complete_todo.py` with two tests that use the
   `authenticated_client` and `todo` fixtures:
   - `test_complete_own_todo`: POST returns 200, and the database row has
     `completed=True`.
   - `test_complete_other_users_todo_returns_404`: a todo made with
     `TodoFactory(user=UserFactory())` returns 404 and stays
     `completed=False`.
4. Run `just openapi` to regenerate `docs/openapi/openapi.json`.
5. In `CHANGELOG.md`, under `## [Unreleased]`, add:
   `- POST /api/todos/{todo_id}/complete marks a todo complete.`

## Do not

- Do not edit files outside `owns`.
- Do not add dependencies.
- Do not hand-edit generated files (`docs/openapi/openapi.json`, migrations,
  `uv.lock`). Regenerate them.

## Verify

```bash
uv run pytest todos/tests/test_complete_todo.py -q --no-cov
grep -c '/api/todos/{todo_id}/complete' docs/openapi/openapi.json
```

Expected: `2 passed`, then a count of `1` or more.

## Done when

- [ ] Every command under Verify gives the expected result.
- [ ] `just gauntlet-quick` passes.
- [ ] The PR changes only paths in `owns`, plus `status: done` in this file.
````
