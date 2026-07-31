---
name: tdd
description: Test-driven development — red-green-refactor loop. Use when building features or fixing bugs test-first, or user mentions "red-green-refactor" or "write tests first".
---

# Test-Driven Development

Red → Green loop. Write the failing test first, then only enough code to pass it. Don't anticipate future tests.

## This repo's testing stack

- **Framework**: pytest + pytest-django
- **Test data**: Factory Boy (not fixtures)
- **Database**: Real test DB (PostgreSQL in CI, SQLite locally)
- **No mocking**: Never mock the ORM. Hit the real database.
- **Client**: `authenticated_client` fixture returns `(client, user)`
- **Location**: `{app}/tests/test_{resource}.py`, factories in `{app}/tests/factories/`

## What a good test is

Tests verify behavior through public interfaces:
- `client.post("/api/todos/", {...})` — tests the API
- `response.status_code == 201` — verifies the contract
- `Todo.objects.filter(user=user).exists()` — verifies the side effect

NOT:
- `mocker.patch("todos.models.Todo.objects.create")` — tests nothing real
- Testing implementation details — tests break on refactor

## Anti-patterns

- **Implementation-coupled** — mocks internal collaborators, tests private methods
- **Tautological** — assertion recomputes the value the same way the code does
- **Horizontal slicing** — all tests first, then all code. Work vertical: one test → one implementation → repeat

## Rules of the loop

- **Red before green.** Failing test first, minimal code to pass.
- **One slice.** One test, one implementation per cycle.
- **Refactoring is review.** Not part of the red-green loop — use `/code-review` after.

## Test template

```python
@pytest.mark.django_db
def test_create_todo(authenticated_client):
    client, user = authenticated_client
    response = client.post(
        "/api/todos/",
        {"title": "Buy milk"},
        content_type="application/json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Buy milk"
    assert Todo.objects.filter(user=user, title="Buy milk").exists()
```
